// Defaults do not construct an SDK client or send any account request.
export const pendingDeletion = Object.freeze({ available: false, deleteAccount: async () => Object.freeze({ status: 'unavailable' }) })
export const pendingFactorRemoval = Object.freeze({ available: false, remove: async () => Object.freeze({ status: 'removal-unavailable' }) })
