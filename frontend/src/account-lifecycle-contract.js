/** Future reviewed server-only lifecycle boundary, not an implemented endpoint.
 * requestId is an idempotency identifier, never ownership or reauthentication proof.
 * The server derives subject/identity, verifies security policy and coordinates both stores.
 * @typedef {Readonly<{status:'unavailable'|'reauthentication-required'|'mfa-required'|'pending'|'disabled'|'deleted'}>} LifecycleOutcome
 */
/** @typedef {Readonly<{
 * disable(options:{signal:AbortSignal, requestId:string}):Promise<LifecycleOutcome>,
 * deleteAccount(options:{signal:AbortSignal, requestId:string}):Promise<LifecycleOutcome>
 * }>} AccountLifecycleService */
/** @type {AccountLifecycleService} */
export const pendingAccountLifecycle = Object.freeze({
  disable: async () => Object.freeze({ status: 'unavailable' }),
  deleteAccount: async () => Object.freeze({ status: 'unavailable' }),
})
