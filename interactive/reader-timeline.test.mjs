import {test} from "node:test";
import assert from "node:assert/strict";
import {activeAt, validateTimeline, seekTarget, isManualPdfNavigation} from "./reader-timeline.mjs";
import {rangeBounds} from "./reader-offline.mjs";

const annotation = {id:"a", start:10, end:20, page:2, type:"rect", rect:[.1,.2,.5,.2], status:"unreviewed"};
const timeline = () => ({version:1, chapter:2, audio_sha256:"audio", pdf_sha256:"pdf", annotations:[structuredClone(annotation)]});
test("offline media seeks support bounded, open and suffix ranges", () => {
  assert.deepEqual(rangeBounds("bytes=3-6",10),[3,6]);
  assert.deepEqual(rangeBounds("bytes=8-",10),[8,9]);
  assert.deepEqual(rangeBounds("bytes=-2",10),[8,9]);
  for (const range of ["bytes=20-30","bytes=5-2","bytes=-0","bytes=0-1,5-6","invalid"]) assert.equal(rangeBounds(range,10),null);
});
test("ten-second controls clamp at audio boundaries", () => {
  assert.equal(seekTarget(5,-10,120),0);
  assert.equal(seekTarget(60,-10,120),50);
  assert.equal(seekTarget(115,10,120),120);
  assert.equal(seekTarget(60,10,NaN),70);
});
test("manual scrolling stops following; automatic scrolling and zoom gestures do not", () => {
  for (const event of [{type:"wheel",deltaY:30},{type:"touchmove",touches:[{}]},{type:"keydown",key:"PageDown"},{type:"pointerdown",button:1}]) {
    assert.equal(isManualPdfNavigation(event),true);
  }
  for (const event of [{type:"scroll"},{type:"wheel",deltaY:30,ctrlKey:true},{type:"touchmove",touches:[{},{}]},{type:"keydown",key:"f",ctrlKey:true},{type:"pointerdown",button:0}]) {
    assert.equal(isManualPdfNavigation(event),false);
  }
  assert.equal(isManualPdfNavigation({type:"pointerdown",button:0},true),true);
});
test("seek forward, backward and across end-exclusive boundaries", () => {
  for (const [time, expected] of [[0,0],[10,1],[19.9,1],[20,0],[12,1],[5,0]]) assert.equal(activeAt([annotation],time).length,expected);
});
test("reject wrong document identity, invalid geometry, pages and timestamps", () => {
  assert.throws(() => validateTimeline(timeline(), {pdfHash:"other"}));
  assert.throws(() => validateTimeline(timeline(), {audioHash:"other"}));
  assert.throws(() => validateTimeline(timeline(), {chapter:3}));
  for (const change of [{end:9},{start:-1},{page:0},{page:3},{rect:[.9,0,.5,.2]},{rect:[0,0,-1,.2]},{type:"script"}]) {
    const t = timeline(); Object.assign(t.annotations[0], change);
    assert.throws(() => validateTimeline(t, {pages:2}));
  }
  assert.equal(validateTimeline(timeline(), {pages:2, duration:30}).annotations.length,1);
});
test("arrows use normalized endpoints; IDs cannot be repeated", () => {
  const t = timeline(); t.annotations[0] = {...annotation,type:"arrow",points:[.1,.2,.8,.9]};
  validateTimeline(t);
  t.annotations.push({...t.annotations[0]}); assert.throws(() => validateTimeline(t));
});
