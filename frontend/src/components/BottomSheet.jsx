import { motion, AnimatePresence } from 'framer-motion';
import RequestCard, { RequestCardSkeleton } from './RequestCard';

export default function BottomSheet({
  requests = [],
  loading,
  selectedRequestId,
  onRequestClick,
  onDragEnd,
  crisisMode = false,
  children,
}) {
  const openAndFundedRequests = requests.filter(
    (r) => r.status === 'open' || r.status === 'funded'
  );
  const claimedRequests = requests.filter((r) => r.status === 'claimed');

  return (
    <motion.div
      className="fixed inset-x-0 bottom-0 z-[1000] pointer-events-none"
      initial={false}
    >
      <div className="pointer-events-auto flex flex-col max-h-[55vh] min-h-[200px]">
        <motion.div
          drag="y"
          dragConstraints={{ top: 0, bottom: 0 }}
          dragElastic={0.1}
          onDragEnd={(_, info) => onDragEnd?.(info)}
          className="bg-slate-900/85 backdrop-blur-xl rounded-t-3xl border-t border-x border-white/10 shadow-2xl flex flex-col max-h-[55vh]"
        >
          <div className="flex justify-center pt-3 pb-2">
            <div className="w-12 h-1 rounded-full bg-white/30" />
          </div>
          <div className="px-4 pb-4 overflow-y-auto flex-1">
            <h2
              className={`text-lg font-semibold mb-3 px-3 py-2 rounded-xl ${
                crisisMode
                  ? 'bg-red-600/90 text-white'
                  : 'text-white'
              }`}
            >
              {crisisMode ? 'Urgent Need' : 'Nearby requests'}
            </h2>
            {children}
            {loading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <RequestCardSkeleton key={i} />
                ))}
              </div>
            ) : (
              <div className="space-y-5">
                <div>
                  <h3 className="text-xs uppercase tracking-wide text-gray-400 mb-2 px-1">
                    Open / Funded
                  </h3>
                  <motion.ul layout className="space-y-3" initial={false}>
                    <AnimatePresence mode="popLayout">
                      {openAndFundedRequests.map((r) => (
                        <li key={r.id}>
                          <RequestCard
                            request={r}
                            onClick={onRequestClick}
                            isSelected={selectedRequestId === r.id}
                          />
                        </li>
                      ))}
                    </AnimatePresence>
                  </motion.ul>
                  {!loading && openAndFundedRequests.length === 0 && (
                    <p className="text-gray-500 text-sm px-1">No open or funded requests in this area.</p>
                  )}
                </div>

                <div>
                  <h3 className="text-xs uppercase tracking-wide text-gray-400 mb-2 px-1">
                    Claimed
                  </h3>
                  <motion.ul layout className="space-y-3" initial={false}>
                    <AnimatePresence mode="popLayout">
                      {claimedRequests.map((r) => (
                        <li key={r.id}>
                          <RequestCard
                            request={r}
                            onClick={onRequestClick}
                            isSelected={selectedRequestId === r.id}
                          />
                        </li>
                      ))}
                    </AnimatePresence>
                  </motion.ul>
                  {!loading && claimedRequests.length === 0 && (
                    <p className="text-gray-500 text-sm px-1">No claimed requests yet.</p>
                  )}
                </div>
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
}
