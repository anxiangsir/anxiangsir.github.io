// Comprehensive Mario physics simulation - test_sim2.js
// Tests:
//   1. Mushroom spawn first-frame collision (vx=1 should NOT immediately reverse)
//   2. Gap at x=2953-3048: player walking in falls and dies
//   3. Big Mario falling from pipe3/pipe4 (y=293) - highest pipes
//   4. Walking off pipe3/pipe4 into gap (near x=2953)

'use strict';

// ── Constants ──────────────────────────────────────────────────────────────
const GROUND_HEIGHT = 418;
const GRAVITY       = 0.4;
const JUMP_GRAVITY  = 0.2;
const JUMP_VEL      = -10;
const FAST_JUMP_VEL = -12.5;
const MAX_Y_VEL     = 11;
const WALK_SPEED    = 3;
const RUN_SPEED     = 5;

// ── Level geometry ──────────────────────────────────────────────────────────
const grounds = [{x: 0, w: 2953}, {x: 3048, w: 635}, {x: 3819, w: 2735}, {x: 6647, w: 2300}];
const pipes = [
  {x: 1202, y: 362, w: 83, h: 66},
  {x: 1631, y: 327, w: 83, h: 112},
  {x: 1973, y: 293, w: 83, h: 136},  // pipe3
  {x: 2445, y: 293, w: 83, h: 136},  // pipe4 (near gap1)
  {x: 6989, y: 362, w: 83, h: 66},
  {x: 7675, y: 362, w: 83, h: 66}
];

// Mushroom block at qbox [901, 292] → y*0.8 = 233.6
const MUSHROOM_BLOCK = {x: 901, y: 292*0.8, w: 34, h: 34};

// ── Helpers ─────────────────────────────────────────────────────────────────
function rectIntersect(a, b) {
  return a.x < b.x+b.w && a.x+a.w > b.x && a.y < b.y+b.h && a.y+a.h > b.y;
}

function checkCols(rect, extraBlocks=[]) {
  const hits = [];
  grounds.forEach(g => {
    const gr = {x: g.x, y: GROUND_HEIGHT, w: g.w, h: 100};
    if(rectIntersect(rect, gr)) hits.push(gr);
  });
  pipes.forEach(p => { if(rectIntersect(rect, p)) hits.push(p); });
  extraBlocks.forEach(b => {
    if(rectIntersect(rect, {x:b.x, y:b.y+b.oy, w:b.w, h:b.h}))
      hits.push({x:b.x, y:b.y+b.oy, w:b.w, h:b.h});
  });
  return hits;
}

// ── Player step (one frame) ─────────────────────────────────────────────────
function stepPlayer(player, keys={}, blocks=[]) {
  const { width, height } = player;

  // Jump intent
  let jumpHeld = false;
  if (keys.jump && !player._jumpWasHeld && player.onGround) {
    player.vy = JUMP_VEL;
    player._jumpWasHeld = true;
    jumpHeld = true;
  } else if (keys.jump && player._jumpWasHeld) {
    jumpHeld = true;
  }
  if (!keys.jump) player._jumpWasHeld = false;

  // vx
  if (keys.right) player.vx = keys.run ? RUN_SPEED : WALK_SPEED;
  else if (keys.left) player.vx = -(keys.run ? RUN_SPEED : WALK_SPEED);
  else player.vx = 0;

  // ── Step 1: Y ──
  player.onGround = false;
  const prevY = player.y;
  player.vy += (player.vy < 0 && jumpHeld) ? JUMP_GRAVITY : GRAVITY;
  if (player.vy > MAX_Y_VEL) player.vy = MAX_Y_VEL;
  player.y += player.vy;

  const yRect = {x: player.x, y: player.y, w: width, h: height};
  const yHits = checkCols(yRect, blocks);
  yHits.forEach(h => {
    const prevBottom = prevY + height;
    const currBottom = player.y + height;
    if (player.vy >= 0 && prevBottom <= h.y + 1 && currBottom > h.y) {
      player.y = h.y - height; player.vy = 0; player.onGround = true;
    } else if (player.vy < 0 && prevY >= h.y + h.h - 1 && player.y < h.y + h.h) {
      player.y = h.y + h.h; player.vy = 0;
    }
  });
  // Hard clamp
  grounds.forEach(g => {
    if (player.x + width > g.x && player.x < g.x + g.w) {
      if (player.y + height > GROUND_HEIGHT) {
        player.y = GROUND_HEIGHT - height; player.vy = 0; player.onGround = true;
      }
    }
  });

  // ── Step 2: X ──
  player.x += player.vx;
  player.x = Math.max(0, player.x);
  const xRect = {x: player.x, y: player.y + 4, w: width, h: height - 8};
  const xHits = checkCols(xRect, blocks);
  if (xHits.length > 0) {
    const h = xHits[0];
    if (player.x + width/2 < h.x + h.w/2) { player.x = h.x - width; player.vx = 0; }
    else { player.x = h.x + h.w; player.vx = 0; }
  }

  if (player.y > 600) player.dead = true;
  return player;
}

// ── Mushroom particle step (one frame) ─────────────────────────────────────
function stepMushroom(p, blocks=[]) {
  // X movement + X collision
  p.x += p.vx;
  const pHitX = checkCols({x: p.x, y: p.y+2, w: 32, h: 28}, blocks);
  if (pHitX.length > 0) { p.vx *= -1; p.x += p.vx * 2; }

  // Y gravity + Y collision
  if (!p.onGround) p.vy += GRAVITY;
  p.y += p.vy;
  p.onGround = false;
  const pHit = checkCols({x: p.x, y: p.y, w: 32, h: 32}, blocks);
  if (pHit.length > 0) {
    if (p.vy >= 0) { p.y = pHit[0].y - 32; p.vy = 0; p.onGround = true; }
    else { p.vy = 0; p.y = pHit[0].y + pHit[0].h; }
  }
  if (p.y > 600) p.dead = true;
  return p;
}

// ── Test runner ─────────────────────────────────────────────────────────────
let passed = 0, failed = 0;
function test(name, fn) {
  try {
    const result = fn();
    if (result === true) {
      console.log(`✅ PASS  ${name}`);
      passed++;
    } else {
      console.log(`❌ FAIL  ${name}  ${result}`);
      failed++;
    }
  } catch(e) {
    console.log(`💥 ERR   ${name}  ${e.message}`);
    failed++;
  }
}

// ── GROUP 1: Mushroom spawn first-frame collision ──────────────────────────
// Block is at {x:901, y:233.6, w:34, h:34}
// Mushroom spawns at {x:901, y:233.6-34=199.6, vx:1}
// The block's rightmost x is 901+34=935, mushroom's x=901, w=32
// X collision rect: {x:901+1=902, y:201.6, w:32, h:28} → covers x=902..934
// Block occupies x=901..935 BUT mushroom rect is y=201.6..229.6
// Block occupies y=233.6..267.6 → NO Y overlap → should NOT collide
console.log('\n── GROUP 1: Mushroom first-frame spawn (vx=1 should not reverse) ──');

test('Mushroom first-frame: no X-collision with parent block', () => {
  const block = {x: 901, y: 292*0.8, w: 34, h: 34, oy: 0};
  // Mushroom spawns just above block
  const p = {x: block.x, y: block.y - 34, vx: 1, vy: 0, onGround: false, dead: false};
  const blockRect = [{x: block.x, y: block.y + block.oy, w: block.w, h: block.h}];

  // Manually check: does the first-frame X rect overlap the block?
  const xCheckRect = {x: p.x + p.vx, y: p.y+2, w: 32, h: 28};
  const hits = checkCols(xCheckRect, blockRect);
  if (hits.length > 0) {
    return `Block hit detected on first frame! hits=${JSON.stringify(hits)}`;
  }
  return true;
});

test('Mushroom moves right 10 frames without reversing (open ground)', () => {
  const block = {x: 901, y: 292*0.8, w: 34, h: 34, oy: 0};
  const p = {x: block.x, y: block.y - 34, vx: 1, vy: 0, onGround: false, dead: false};
  for (let i = 0; i < 10; i++) {
    stepMushroom(p, [{x: block.x, y: block.y + block.oy, w: block.w, h: block.h}]);
    if (p.vx < 0) return `Reversed to vx<0 at frame ${i+1}, p=${JSON.stringify({x:p.x,vx:p.vx})}`;
  }
  if (p.x <= block.x) return `Mushroom didn't move right: x=${p.x}`;
  return true;
});

test('Mushroom lands on ground eventually', () => {
  const block = {x: 901, y: 292*0.8, w: 34, h: 34, oy: 0};
  let p = {x: block.x, y: block.y - 34, vx: 1, vy: 0, onGround: false, dead: false};
  for (let i = 0; i < 60; i++) {
    stepMushroom(p, [{x: block.x, y: block.y + block.oy, w: block.w, h: block.h}]);
    if (p.onGround) return true;
  }
  return `Mushroom never landed: y=${p.y} onGround=${p.onGround}`;
});

// ── GROUP 2: Gap at x=2953-3048 ────────────────────────────────────────────
// Ground segment 0: {x:0, w:2953} → ends at x=2953
// Ground segment 1: {x:3048, w:635} → starts at x=3048
// Gap: [2953, 3048)
console.log('\n── GROUP 2: Player walking into Gap (x=2953..3048) ──');

test('Player at gap edge (x=2900) on ground, walks right, falls into gap', () => {
  const player = {x: 2900, y: GROUND_HEIGHT - 32, vx: 0, vy: 0, width: 32, height: 32, onGround: true, dead: false, _jumpWasHeld: false};
  let fellInGap = false;
  for (let i = 0; i < 100; i++) {
    stepPlayer(player, {right: true}, []);
    // Player is in gap x range and not on ground → falling
    if (player.x + player.width > 2953 && player.x < 3048 && !player.onGround && player.vy > 0) {
      fellInGap = true;
    }
    if (player.dead) return true; // killed by falling
    if (player.onGround && player.x >= 3048) return true; // survived by crossing
  }
  if (fellInGap) return true; // was falling in gap, eventually died or crossed
  return `Never fell in gap: x=${player.x.toFixed(1)} y=${player.y.toFixed(1)} onGround=${player.onGround} dead=${player.dead}`;
});

test('Player mid-gap (x=2990) falls and dies', () => {
  const player = {x: 2990, y: GROUND_HEIGHT - 32 - 1, vx: 0, vy: 1, width: 32, height: 32, onGround: false, dead: false, _jumpWasHeld: false};
  for (let i = 0; i < 200; i++) {
    stepPlayer(player, {}, []);
    if (player.dead) return true;
  }
  return `Player didn't die: x=${player.x.toFixed(1)} y=${player.y.toFixed(1)} onGround=${player.onGround}`;
});

test('Player running (vx=5) from x=2900 falls into gap (not skip over)', () => {
  const player = {x: 2900, y: GROUND_HEIGHT - 32, vx: 0, vy: 0, width: 32, height: 32, onGround: true, dead: false, _jumpWasHeld: false};
  let wasInGap = false;
  for (let i = 0; i < 80; i++) {
    stepPlayer(player, {right: true, run: true}, []);
    if (player.x > 2953 && player.x < 3048 - 32) wasInGap = true;
    if (player.dead) return wasInGap ? true : `Died but never entered gap: x history check`;
    if (player.onGround && player.x >= 3048) {
      // crossed gap safely (possible for running player if gap < player width... gap=95, player=32, should fall)
      return `Player skipped over gap: x=${player.x.toFixed(1)}`;
    }
  }
  return `Player didn't die or cross: x=${player.x.toFixed(1)} y=${player.y.toFixed(1)} onGround=${player.onGround} dead=${player.dead}`;
});

// ── GROUP 3: Big Mario falling from highest pipes (pipe3/pipe4 y=293) ──────
// pipe3: {x:1973, y:293, w:83, h:136}, top=293
// pipe4: {x:2445, y:293, w:83, h:136}, top=293
// Big Mario height=64, so standing on pipe3 top: player.y = 293-64 = 229
console.log('\n── GROUP 3: Big Mario from pipe3/pipe4 (y=293, highest) ──');

test('Big Mario lands on pipe3 top from above', () => {
  // Drop from y=200 (above pipe3 top=293)
  const player = {x: 1990, y: 200, vx: 0, vy: 5, width: 32, height: 64, onGround: false, dead: false, _jumpWasHeld: false};
  for (let i = 0; i < 40; i++) {
    stepPlayer(player, {}, []);
    if (player.onGround && Math.abs(player.y - (293 - 64)) < 2) return true;
    if (player.dead) return `Player died unexpectedly at y=${player.y.toFixed(1)}`;
  }
  return `Did not land on pipe3 top: y=${player.y.toFixed(1)} onGround=${player.onGround}`;
});

test('Big Mario walks off pipe3 (right edge) and lands on ground', () => {
  // Start on pipe3: x=1973, y=293 → player.y = 293-64=229
  const player = {x: 1973, y: 293-64, vx: 0, vy: 0, width: 32, height: 64, onGround: true, dead: false, _jumpWasHeld: false};
  for (let i = 0; i < 100; i++) {
    stepPlayer(player, {right: true}, []);
    if (player.onGround && player.y >= GROUND_HEIGHT - 65) return true; // landed on ground
    if (player.dead) return `Player died: x=${player.x.toFixed(1)} y=${player.y.toFixed(1)}`;
  }
  return `Did not reach ground: y=${player.y.toFixed(1)} onGround=${player.onGround}`;
});

test('Big Mario on pipe4 (near gap1 at x=2953), walks right into gap and dies', () => {
  // pipe4: {x:2445, y:293, w:83, h:136}, right edge at x=2445+83=2528
  // After pipe4, next ground is 2953. Gap is 2953-3048.
  // Player walks right from pipe4, hits ground, continues to gap
  const player = {x: 2445 + 83 + 1, y: GROUND_HEIGHT - 65, vx: 0, vy: 0, width: 32, height: 64, onGround: true, dead: false, _jumpWasHeld: false};
  for (let i = 0; i < 300; i++) {
    stepPlayer(player, {right: true}, []);
    if (player.dead) return true;
    if (player.x > 3200) return `Player crossed gap without dying: x=${player.x.toFixed(1)}`;
  }
  return `Player didn't die: x=${player.x.toFixed(1)} y=${player.y.toFixed(1)} onGround=${player.onGround}`;
});

test('Small Mario falls from pipe3 top, no clipping underground', () => {
  // Drop Big Mario from just above pipe3
  const player = {x: 2000, y: 230, vx: 0, vy: 3, width: 32, height: 32, onGround: false, dead: false, _jumpWasHeld: false};
  let minY = Infinity;
  for (let i = 0; i < 60; i++) {
    stepPlayer(player, {}, []);
    if (player.y + player.height > minY) minY = player.y + player.height;
    if (player.dead) return `Player died: y=${player.y}`;
  }
  // Should land on pipe3 top=293 or ground=418
  const bottom = player.y + player.height;
  const underground = bottom > GROUND_HEIGHT + 2;
  if (underground) return `Player underground: bottom=${bottom.toFixed(1)}`;
  return true;
});

// ── GROUP 4: Walk off pipe3 right edge directly into gap ───────────────────
// pipe3 right edge = 1973+83 = 2056. Gap starts at 2953. So walking right from
// pipe3 the player lands on ground, then continues to gap. Already covered in GROUP 3.
// Test: walk off pipe3 LEFT edge - should land on ground (x<1973) safely.
console.log('\n── GROUP 4: Pipe3 left edge drop ──');

test('Small Mario walks off pipe3 LEFT edge, lands on ground safely', () => {
  // Start on pipe3, walk left off it
  const player = {x: 1973, y: 293-32, vx: 0, vy: 0, width: 32, height: 32, onGround: true, dead: false, _jumpWasHeld: false};
  for (let i = 0; i < 80; i++) {
    stepPlayer(player, {left: true}, []);
    if (player.onGround && player.y >= GROUND_HEIGHT - 33 && player.x < 1973) return true;
    if (player.dead) return `Player died: x=${player.x.toFixed(1)} y=${player.y.toFixed(1)}`;
  }
  return `Did not land on ground: y=${player.y.toFixed(1)} onGround=${player.onGround} x=${player.x.toFixed(1)}`;
});

test('No underground after fast-fall from height (pipe3 top, vy=11)', () => {
  // Worst case: max fall speed from pipe3 top
  const player = {x: 2000, y: 293-33, vx: 0, vy: 11, width: 32, height: 32, onGround: false, dead: false, _jumpWasHeld: false};
  for (let i = 0; i < 20; i++) {
    stepPlayer(player, {}, []);
    if (player.y + 32 > GROUND_HEIGHT + 2 && !player.dead) {
      return `Underground at frame ${i}: bottom=${(player.y+32).toFixed(1)} > ${GROUND_HEIGHT}`;
    }
    if (player.dead) return true;
  }
  return true;
});

// ── SUMMARY ────────────────────────────────────────────────────────────────
console.log(`\n── SUMMARY: ${passed} passed, ${failed} failed ──`);
process.exit(failed > 0 ? 1 : 0);
