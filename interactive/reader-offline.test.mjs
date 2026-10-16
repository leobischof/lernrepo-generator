import test from 'node:test';
import assert from 'node:assert/strict';
import {setupOffline} from './reader-offline.mjs';

test('an updated worker reloads an already controlled page once', async () => {
  const originalNavigator = Object.getOwnPropertyDescriptor(globalThis,'navigator');
  const originalLocation = globalThis.location;
  const serviceWorker = new EventTarget();
  serviceWorker.controller = {};
  let reloads = 0;
  serviceWorker.register = async () => ({});
  serviceWorker.ready = Promise.resolve({active:{postMessage(){}}});
  Object.defineProperty(globalThis,'navigator',{configurable:true,value:{serviceWorker}});
  globalThis.isSecureContext = true;
  globalThis.location = {reload(){reloads++;}};
  try {
    const button = {addEventListener(){},disabled:true}, status = {};
    await setupOffline({button,status,getChapter:()=>({number:1})});
    serviceWorker.dispatchEvent(new Event('controllerchange'));
    serviceWorker.dispatchEvent(new Event('controllerchange'));
    assert.equal(reloads,1);
    assert.equal(button.disabled,false);
  } finally {
    if (originalNavigator) Object.defineProperty(globalThis,'navigator',originalNavigator);
    else delete globalThis.navigator;
    globalThis.location = originalLocation;
    delete globalThis.isSecureContext;
  }
});

test('embedded chapter files do not register a service worker', async () => {
  globalThis.LEARNREPO_EMBEDDED = {};
  const button = {}, status = {};
  try {
    await setupOffline({button,status,getChapter:()=>null});
    assert.equal(button.hidden,true);
    assert.match(status.textContent,/vollständig/);
  } finally { delete globalThis.LEARNREPO_EMBEDDED; }
});
