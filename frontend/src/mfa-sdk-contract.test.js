// Characterize the actual pinned SDK with mocked HTTP and locally signed tokens.
// These tests do not attest hosted inventory completeness or authorize any policy change.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { passwordFixture, signingFixture, json, subject } from './password-test-support.js'
const installed=JSON.parse(readFileSync(new URL('../node_modules/@supabase/auth-js/package.json',import.meta.url)))
assert.equal(installed.version,'2.119.0')
const factor={id:'aaaaaaaa-1234-4234-9234-123456789abc',factor_type:'totp',status:'verified'}
for(const [label,factors,present,all,verified] of [
 ['omitted',undefined,false,0,0],['null',null,true,0,0],['explicit empty',[],true,0,0],
 ['verified TOTP',[factor],true,1,1],['unverified TOTP',[{...factor,status:'unverified'}],true,1,0],
 ['unsupported verified factor',[{...factor,factor_type:'future_type'}],true,1,0],
]) test('real SDK normalization: '+label,async t=>{
 const keys=await signingFixture(), signed=await keys.sign({},'password')
 const raw={id:subject,is_anonymous:false,...(present?{factors}:{})}
 const f=await passwordFixture(t,url=>json(url.pathname.endsWith('/jwks.json')?keys.jwks:raw))
 assert.equal((await f.client.auth.setSession(signed)).error,null)
 const observed=await f.client.auth.getUser(signed.access_token)
 assert.equal(Object.hasOwn(observed.data.user,'factors'),present)
 const before=f.calls.length, listed=await f.client.auth.mfa.listFactors()
 assert.equal(listed.error,null);assert.equal(listed.data.all.length,all);assert.equal(listed.data.totp.length,verified)
 assert.deepEqual(f.calls.slice(before),['/auth/v1/user'])
 const aal=await f.client.auth.mfa.getAuthenticatorAssuranceLevel(signed.access_token)
 assert.equal(aal.error,null);assert.equal(aal.data.currentLevel,'aal1')
 assert.equal(aal.data.nextLevel,factors?.some?.(x=>x.status==='verified')?'aal2':'aal1')
})
for(const status of [401,429,500])test('real SDK does not return successful inventory on HTTP'+status,async t=>{
 const keys=await signingFixture(), signed=await keys.sign({},'password');let failure=false
 const f=await passwordFixture(t,()=>failure?json({code:'offline_failure',message:'offline provider failure'},status):json({id:subject}))
 assert.equal((await f.client.auth.setSession(signed)).error,null);failure=true
 const result=await f.client.auth.mfa.listFactors()
 assert.equal(result.data,null);assert.ok(result.error)
})
test('real SDK malformed inventory is not a successful empty inventory',async t=>{
 const keys=await signingFixture(), signed=await keys.sign({},'password')
 const f=await passwordFixture(t,()=>json({id:subject,factors:{}}))
 assert.equal((await f.client.auth.setSession(signed)).error,null)
 await assert.rejects(()=>f.client.auth.mfa.listFactors(),TypeError)
})
