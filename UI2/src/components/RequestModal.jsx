import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { fetchRequestDetail, donateToRequest, claimRequest } from '../api/requests';

const CATEGORY_ICONS = {
  meds: '💊',
  groceries: '🛒',
  shelter: '🏠',
  transport: '🚗',
  other: '📦',
};

const PRESET_AMOUNTS = [5, 10, 25];

export default function RequestModal({ requestId, onClose, onDonated, onClaimed }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [donating, setDonating] = useState(false);
  const [claiming, setClaiming] = useState(false);
  const [customAmount, setCustomAmount] = useState('');
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!requestId) return;
    setLoading(true);
    setError(null);
    fetchRequestDetail(requestId)
      .then((d) => setDetail(d.request))
      .catch((e) => setError(e.response?.data?.detail || 'Failed to load'))
      .finally(() => setLoading(false));
  }, [requestId]);

  const handleDonate = async (amount) => {
    const num = typeof amount === 'number' ? amount : parseFloat(customAmount);
    if (!num || num <= 0) return;
    setDonating(true);
    setError(null);
    try {
      const res = await donateToRequest(requestId, num);
      setDetail((prev) => (prev ? { ...prev, ...res.request } : res.request));
      onDonated?.(res);
    } catch (e) {
      setError(e.response?.data?.detail || 'Donation failed');
    } finally {
      setDonating(false);
      setCustomAmount('');
    }
  };

  const handleClaim = async () => {
    setClaiming(true);
    setError(null);
    try {
      await claimRequest(requestId);
      const res = await fetchRequestDetail(requestId);
      setDetail(res.request);
      onClaimed?.();
    } catch (e) {
      setError(e.response?.data?.detail || 'Claim failed');
    } finally {
      setClaiming(false);
    }
  };

  const progress = detail ? Math.min(1, detail.progress ?? 0) : 0;
  const isFunded = detail?.status === 'funded';
  const isClaimed = detail?.status === 'claimed' || detail?.status === 'delivered';
  const canClaim = isFunded && !isClaimed;
  const googleMapsUrl = detail
    ? `https://www.google.com/maps/dir/?api=1&destination=${detail.lat},${detail.lng}`
    : '#';

  if (!requestId) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[1100] flex items-end sm:items-center justify-center p-0 sm:p-4"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, y: 100 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 100 }}
          transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          className="w-full max-w-lg rounded-t-3xl sm:rounded-3xl bg-slate-900/95 backdrop-blur-xl border border-white/10 shadow-2xl max-h-[90vh] overflow-hidden"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex justify-center pt-3 pb-2 border-b border-white/10">
            <div className="w-12 h-1 rounded-full bg-white/30" />
          </div>
          <div className="overflow-y-auto max-h-[85vh] p-4">
            {loading ? (
              <div className="animate-pulse space-y-4">
                <div className="h-8 w-3/4 bg-white/20 rounded" />
                <div className="h-4 w-full bg-white/10 rounded" />
                <div className="h-20 bg-white/10 rounded" />
              </div>
            ) : error && !detail ? (
              <p className="text-red-400">{error}</p>
            ) : detail ? (
              <>
                <div className="flex items-start justify-between gap-2 mb-4">
                  <div className="flex items-center gap-3">
                    <span className="text-3xl">
                      {CATEGORY_ICONS[detail.category] || '📦'}
                    </span>
                    <div>
                      <h2 className="text-xl font-semibold text-white capitalize">
                        {detail.category}
                      </h2>
                      <p className="text-sm text-gray-400">
                        Urgency: {detail.urgency_window} · Severity {detail.severity}/5
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={onClose}
                    className="p-2 rounded-full hover:bg-white/10 text-gray-400"
                    aria-label="Close"
                  >
                    ✕
                  </button>
                </div>

                <p className="text-gray-300 text-sm whitespace-pre-wrap mb-4">
                  {detail.raw_text}
                </p>

                {detail.rank_reason && (
                  <div
                    className="flex items-center gap-2 text-xs text-amber-200/90 bg-amber-500/10 rounded-lg px-3 py-2 mb-4"
                    title="AI prioritized this request by urgency, severity, and funding gap — not profit."
                  >
                    <span>💡</span>
                    <span>AI prioritized: {detail.rank_reason}</span>
                  </div>
                )}
                <div className="flex flex-wrap gap-2 mb-4">
                  {detail.severity >= 4 && (
                    <span className="text-xs bg-amber-500/20 text-amber-200 rounded-full px-2 py-1">
                      High need
                    </span>
                  )}
                  <span className="text-xs bg-slate-500/20 text-slate-300 rounded-full px-2 py-1">
                    Vulnerability-aware ranking
                  </span>
                  <span className="text-xs text-gray-500 border border-white/10 rounded-full px-2 py-1">
                    👴 Elderly
                  </span>
                  <span className="text-xs text-gray-500 border border-white/10 rounded-full px-2 py-1">
                    👶 Infant
                  </span>
                  <span className="text-xs text-gray-500 border border-white/10 rounded-full px-2 py-1">
                    ♿ Disabled
                  </span>
                </div>

                {detail.items?.length > 0 && (
                  <ul className="text-sm text-gray-300 mb-4 space-y-1">
                    {detail.items.map((item, i) => (
                      <li key={i}>
                        {item.qty} {item.unit} {item.name}
                        {item.notes ? ` — ${item.notes}` : ''}
                      </li>
                    ))}
                  </ul>
                )}

                <div className="mb-4">
                  <div className="flex justify-between text-sm text-gray-400 mb-1">
                    <span>Funding progress</span>
                    <span>
                      ${(detail.funded_amount ?? 0).toFixed(0)} / $
                      {(detail.funding_goal ?? 0).toFixed(0)}
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-white/20 overflow-hidden">
                    <motion.div
                      className="h-full rounded-full bg-emerald-400"
                      initial={false}
                      animate={{ width: `${progress * 100}%` }}
                      transition={{ duration: 0.5, ease: 'easeOut' }}
                    />
                  </div>
                </div>

                {error && (
                  <p className="text-red-400 text-sm mb-4">{error}</p>
                )}

                {detail.status === 'open' && (
                  <div className="space-y-3">
                    <p className="text-sm text-gray-400">Donate</p>
                    <div className="flex gap-2 flex-wrap">
                      {PRESET_AMOUNTS.map((amt) => (
                        <button
                          key={amt}
                          type="button"
                          disabled={donating}
                          onClick={() => handleDonate(amt)}
                          className="px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-white font-medium"
                        >
                          ${amt}
                        </button>
                      ))}
                      <div className="flex gap-2 flex-1 min-w-[120px]">
                        <input
                          type="number"
                          min="1"
                          step="1"
                          placeholder="Other"
                          value={customAmount}
                          onChange={(e) => setCustomAmount(e.target.value)}
                          className="flex-1 rounded-xl bg-white/10 border border-white/20 px-3 py-2 text-white placeholder-gray-500 text-sm"
                        />
                        <button
                          type="button"
                          disabled={donating || !customAmount}
                          onClick={() => handleDonate()}
                          className="px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-white font-medium text-sm"
                        >
                          Give
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {canClaim && (
                  <div className="mt-4 space-y-2">
                    <button
                      type="button"
                      disabled={claiming}
                      onClick={handleClaim}
                      className="w-full py-3 rounded-xl bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-white font-semibold"
                    >
                      {claiming ? 'Claiming…' : 'Claim'}
                    </button>
                    <a
                      href={googleMapsUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block w-full py-3 rounded-xl bg-white/10 hover:bg-white/20 text-center text-white font-medium"
                    >
                      Open in Google Maps
                    </a>
                  </div>
                )}

                {isClaimed && (
                  <a
                    href={googleMapsUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block w-full py-3 rounded-xl bg-amber-500 hover:bg-amber-600 text-center text-white font-semibold mt-4"
                  >
                    Open in Google Maps
                  </a>
                )}
              </>
            ) : null}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
