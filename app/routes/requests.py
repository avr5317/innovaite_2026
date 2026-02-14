from fastapi import APIRouter, Header, HTTPException, Query
from datetime import datetime, timezone
from bson import ObjectId
from pymongo import ReturnDocument

from app.db import requests_col, donations_col
from app.models import CreateRequestIn, RequestDetailOut, DonateIn, DonateOut, RankOut, ClaimOut
from app.triage import compute_funding_goal, progress_ratio, rank_score, rank_reason_text

router = APIRouter()

def require_device(x_device_token: str | None) -> str:
    if not x_device_token:
        raise HTTPException(status_code=400, detail="Missing X-Device-Token")
    return x_device_token

def oid(s: str) -> ObjectId:
    try:
        return ObjectId(s)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid id")

def public_location(loc: dict) -> dict:
    # Optional blur: keep as-is for MVP
    return {"lat": float(loc["lat"]), "lng": float(loc["lng"])}

@router.post("/requests")
def create_request(payload: CreateRequestIn, x_device_token: str | None = Header(default=None, alias="X-Device-Token")):
    device = require_device(x_device_token)

    funding_goal = compute_funding_goal(payload.estimated_total, payload.requester_afford)
    funded_amount = 0.0
    prog = progress_ratio(funded_amount, funding_goal)

    now = datetime.now(timezone.utc)
    rscore = rank_score(payload.urgency_window, payload.severity, prog, now)
    rreason = rank_reason_text(payload.urgency_window, payload.severity, prog, now)

    doc = {
        "created_at": now,
        "updated_at": now,
        "created_by": device,

        "raw_text": payload.raw_text,
        "category": payload.category,
        "urgency_window": payload.urgency_window,
        "severity": payload.severity,
        "items": [it.model_dump() for it in payload.items],

        "location": public_location(payload.location.model_dump()),
        "status": "open",

        "estimated_total": round(float(payload.estimated_total), 2),
        "requester_afford": round(float(payload.requester_afford), 2),
        "funding_goal": round(float(funding_goal), 2),
        "funded_amount": 0.0,
        "progress": prog,

        "rank_score": rscore,
        "rank_reason": rreason,
        "claim": None,
    }

    res = requests_col.insert_one(doc)
    return {"request": {"id": str(res.inserted_id), **{k: doc[k] for k in [
        "status","funding_goal","funded_amount","progress","rank_score"
    ]}}}

@router.get("/requests")
def list_requests(
    bbox: str | None = Query(default=None, description="minLat,minLng,maxLat,maxLng"),
    status: str | None = Query(default=None, description="open|funded|claimed|delivered"),
    sort: str = Query(default="rank", description="rank|new"),
    limit: int = Query(default=200, ge=1, le=1000),
):
    q = {}
    if status:
        q["status"] = status

    if bbox:
        try:
            minLat, minLng, maxLat, maxLng = [float(x) for x in bbox.split(",")]
        except Exception:
            raise HTTPException(status_code=400, detail="bbox must be minLat,minLng,maxLat,maxLng")
        q["location.lat"] = {"$gte": minLat, "$lte": maxLat}
        q["location.lng"] = {"$gte": minLng, "$lte": maxLng}

    proj = {
        "category": 1, "urgency_window": 1, "severity": 1, "status": 1,
        "location": 1, "estimated_total": 1, "requester_afford": 1,
        "funding_goal": 1, "funded_amount": 1, "progress": 1,
        "rank_score": 1
    }

    cursor = requests_col.find(q, proj)
    if sort == "new":
        cursor = cursor.sort("created_at", -1)
    else:
        cursor = cursor.sort("rank_score", -1).sort("created_at", -1)

    cursor = cursor.limit(limit)

    out = []
    for d in cursor:
        out.append({
            "id": str(d["_id"]),
            "category": d["category"],
            "urgency_window": d["urgency_window"],
            "severity": d["severity"],
            "status": d["status"],
            "lat": d["location"]["lat"],
            "lng": d["location"]["lng"],
            "estimated_total": float(d["estimated_total"]),
            "requester_afford": float(d["requester_afford"]),
            "funding_goal": float(d["funding_goal"]),
            "funded_amount": float(d["funded_amount"]),
            "progress": float(d["progress"]),
            "rank_score": float(d.get("rank_score", 0.0)),
        })

    return {"requests": out}

@router.get("/requests/{request_id}")
def get_request(request_id: str):
    d = requests_col.find_one({"_id": oid(request_id)})
    if not d:
        raise HTTPException(status_code=404, detail="not found")
    return {
        "request": {
            "id": str(d["_id"]),
            "raw_text": d["raw_text"],
            "category": d["category"],
            "urgency_window": d["urgency_window"],
            "severity": d["severity"],
            "status": d["status"],
            "lat": d["location"]["lat"],
            "lng": d["location"]["lng"],
            "items": d.get("items", []),
            "estimated_total": float(d["estimated_total"]),
            "requester_afford": float(d["requester_afford"]),
            "funding_goal": float(d["funding_goal"]),
            "funded_amount": float(d["funded_amount"]),
            "progress": float(d["progress"]),
            "rank_score": float(d.get("rank_score", 0.0)),
            "rank_reason": d.get("rank_reason", ""),
            "claim": d.get("claim"),
            "created_at": d["created_at"],
            "updated_at": d["updated_at"],
        }
    }

@router.post("/requests/{request_id}/donate", response_model=DonateOut)
def donate(
    request_id: str,
    payload: DonateIn,
    x_device_token: str | None = Header(default=None, alias="X-Device-Token"),
):
    donor = require_device(x_device_token)
    rid = oid(request_id)
    amount = round(float(payload.amount), 2)

    # 1) Insert donation record
    donations_col.insert_one({
        "request_id": rid,
        "donor_id": donor,
        "amount": amount,
        "created_at": datetime.now(timezone.utc),
    })

    # 2) Atomically increment funded_amount
    updated = requests_col.find_one_and_update(
        {"_id": rid, "status": {"$in": ["open", "funded"]}},
        {"$inc": {"funded_amount": amount}, "$set": {"updated_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="request not open/fundable")

    goal = float(updated["funding_goal"])
    funded = float(updated["funded_amount"])
    prog = progress_ratio(funded, goal)

    new_status = updated["status"]
    if goal <= 0:
        prog = 1.0
        new_status = "funded"
    elif funded >= goal:
        new_status = "funded"

    # 3) Set progress + possibly status, and recompute rank fields
    rscore = rank_score(updated["urgency_window"], int(updated["severity"]), prog, updated["created_at"])
    rreason = rank_reason_text(updated["urgency_window"], int(updated["severity"]), prog, updated["created_at"])

    updated2 = requests_col.find_one_and_update(
        {"_id": rid},
        {"$set": {"progress": prog, "status": new_status, "rank_score": rscore, "rank_reason": rreason, "updated_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
    )

    return DonateOut(request={
        "id": request_id,
        "funded_amount": float(updated2["funded_amount"]),
        "funding_goal": float(updated2["funding_goal"]),
        "progress": float(updated2["progress"]),
        "status": updated2["status"],
        "rank_score": float(updated2.get("rank_score", 0.0)),
        "rank_reason": updated2.get("rank_reason", "")
    })

@router.post("/ai/rank", response_model=RankOut)
def ai_rank():
    # Recompute rank_score for all OPEN requests (or open+funded if you want)
    q = {"status": {"$in": ["open", "funded"]}}
    cursor = requests_col.find(q, {"urgency_window": 1, "severity": 1, "progress": 1, "created_at": 1})
    updated_count = 0
    now = datetime.now(timezone.utc)

    for d in cursor:
        prog = float(d.get("progress", 0.0))
        rscore = rank_score(d["urgency_window"], int(d["severity"]), prog, d["created_at"])
        rreason = rank_reason_text(d["urgency_window"], int(d["severity"]), prog, d["created_at"])
        requests_col.update_one({"_id": d["_id"]}, {"$set": {"rank_score": rscore, "rank_reason": rreason, "updated_at": now}})
        updated_count += 1

    return RankOut(updated=updated_count)

@router.post("/requests/{request_id}/claim", response_model=ClaimOut)
def claim(
    request_id: str,
    x_device_token: str | None = Header(default=None, alias="X-Device-Token"),
):
    helper = require_device(x_device_token)
    rid = oid(request_id)

    # Only allow claim if funded and not already claimed
    updated = requests_col.find_one_and_update(
        {"_id": rid, "status": "funded", "claim": None},
        {"$set": {
            "status": "claimed",
            "claim": {"helper_id": helper, "claimed_at": datetime.now(timezone.utc)},
            "updated_at": datetime.now(timezone.utc)
        }},
        return_document=ReturnDocument.AFTER,
    )

    if not updated:
        raise HTTPException(status_code=409, detail="not_claimable")

    return ClaimOut(request={"id": request_id, "status": "claimed", "claim": updated["claim"]})

@router.post("/requests/{request_id}/delivered")
def delivered(
    request_id: str,
    x_device_token: str | None = Header(default=None, alias="X-Device-Token"),
):
    helper = require_device(x_device_token)
    rid = oid(request_id)

    d = requests_col.find_one({"_id": rid})
    if not d:
        raise HTTPException(status_code=404, detail="not found")

    claim = d.get("claim")
    if not claim or claim.get("helper_id") != helper:
        raise HTTPException(status_code=403, detail="not_claiming_helper")

    updated = requests_col.find_one_and_update(
        {"_id": rid, "status": "claimed"},
        {"$set": {"status": "delivered", "updated_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(status_code=409, detail="wrong_state")

    return {"request": {"id": request_id, "status": "delivered"}}
