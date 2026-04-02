    (function() {
      const canvas = document.getElementById('marioCanvas');
      const ctx = canvas.getContext('2d');
      const startBtn = document.getElementById('marioStartBtn');
      
      const sprMario = new Image(); sprMario.src = 'assets/img/mario_bros.png';
      const sprEnemies = new Image(); sprEnemies.src = 'assets/img/smb_enemies_sheet.png';
      const sprItems = new Image(); sprItems.src = 'assets/img/item_objects.png';
      const sprTiles = new Image(); sprTiles.src = 'assets/img/tile_set.png';

      function drawSprite(img, sx, sy, sw, sh, dx, dy, dw, dh) {
        ctx.drawImage(img, sx, sy, sw, sh, dx, dy, dw, dh);
      }

      let audioCtx = null;
      const soundBuffers = {};
      const SOUNDS = {
        jump: 'https://archive.org/download/mario_nes_snes_sounds/Mario%201%20-%20Jump.ogg',
        coin: 'https://archive.org/download/mario_nes_snes_sounds/coin%20%28nes%29.ogg',
        stomp: 'https://archive.org/download/mario_nes_snes_sounds/stomp.ogg',
        mushroom: 'https://archive.org/download/mario_nes_snes_sounds/Power%20Up%20%28nes%29.ogg',
        death: 'https://archive.org/download/mario_nes_snes_sounds/Mario%201%20-%20Die.ogg',
        levelclear: 'https://archive.org/download/mario_nes_snes_sounds/Mario%201%20-%20Win%20Stage.ogg'
      };

      function initAudio() {
        if(audioCtx) return;
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        Object.entries(SOUNDS).forEach(([name, url]) => {
          fetch(url)
            .then(r => r.arrayBuffer())
            .then(buf => audioCtx.decodeAudioData(buf))
            .then(decoded => { soundBuffers[name] = decoded; })
            .catch(() => {});
        });
      }

      function playSound(name) {
        if(!audioCtx || !soundBuffers[name]) return;
        if(audioCtx.state === 'suspended') audioCtx.resume();
        const src = audioCtx.createBufferSource();
        src.buffer = soundBuffers[name];
        src.connect(audioCtx.destination);
        src.start(0);
      }

      const GRAVITY = 0.4;
      const JUMP_GRAVITY = 0.2;
      const JUMP_VEL = -10;
      const FAST_JUMP_VEL = -12.5;
      const MAX_Y_VEL = 11;
      const WALK_SPEED = 3;
      const RUN_SPEED = 5;
      const WALK_ACCEL = 0.15;
      const GROUND_HEIGHT = 418;
      
      let state = 'TITLE'; 
      let frameId = null;
      let score = 0, coins = 0, time = 300, lives = 3;
      let cameraX = 0;
      let timeTimer = 0, deadTimer = 0, completeTimer = 0;
      
      const keys = { left: false, right: false, jump: false, run: false };
      let jumpHeld = false;
      
      let grounds = [], pipes = [], blocks = [], enemies = [], particles = [], flagpole = null;
      
      const player = {
        x: 50, y: 100, width: 24, height: 32, vx: 0, vy: 0,
        facing: 1, onGround: false, isBig: false, dead: false,
        animFrame: 0, invulnTimer: 0
      };

      const C = {
        SKY: '#5C94FC', DIRT: '#E69C24', BRICK: '#C84B00', QBOX: '#E8A000',
        QBOX_HIT: '#C84B00', PIPE: '#008000', PIPE_OUTLINE: '#00A800',
        RED: '#CC0000', SKIN: '#FCA044', BLUE: '#0000CC', SHOE: '#6B3300'
      };

      document.addEventListener('keydown', e => {
        initAudio();
        if(e.code === 'ArrowLeft' || e.code === 'KeyA') keys.left = true;
        if(e.code === 'ArrowRight' || e.code === 'KeyD') keys.right = true;
        if(e.code === 'Space' || e.code === 'ArrowUp' || e.code === 'KeyW') {
          if(!keys.jump) jumpHeld = true;
          keys.jump = true;
          if(state === 'TITLE' || state === 'COMPLETE') startGame();
          if(state === 'PLAYING') e.preventDefault();
        }
        if(e.code === 'ShiftLeft' || e.code === 'ShiftRight') keys.run = true;
      });

      document.addEventListener('keyup', e => {
        if(e.code === 'ArrowLeft' || e.code === 'KeyA') keys.left = false;
        if(e.code === 'ArrowRight' || e.code === 'KeyD') keys.right = false;
        if(e.code === 'Space' || e.code === 'ArrowUp' || e.code === 'KeyW') keys.jump = false;
        if(e.code === 'ShiftLeft' || e.code === 'ShiftRight') keys.run = false;
      });

      function initLevel() {
        grounds = [{x: 0, w: 2953}, {x: 3048, w: 635}, {x: 3819, w: 2735}, {x: 6647, w: 2300}];
        pipes = [
          {x: 1202, y: 362, w: 83, h: 66}, {x: 1631, y: 327, w: 83, h: 112},
          {x: 1973, y: 293, w: 83, h: 136}, {x: 2445, y: 293, w: 83, h: 136},
          {x: 6989, y: 362, w: 83, h: 66}, {x: 7675, y: 362, w: 83, h: 66}
        ];
        
        blocks = [];
        const brickCoords = [[858,292], [944,292], [1030,292], [3299,292], [3385,292], 
          [3430,154], [3473,154], [3516,154], [3559,154], [3602,154], [3645,154], 
          [3688,154], [3731,154], [3901,154], [3944,154], [3987,154], [4030,292, 'coins', 6], 
          [4287,292], [4330,292, 'star', 1], [5058,292], [5187,154], [5230,154], 
          [5273,154], [5488,154], [5574,154], [5617,154], [5531,292], [5574,292], 
          [7202,292], [7245,292], [7331,292]];
        
        brickCoords.forEach(c => blocks.push({x: c[0], y: c[1]*0.8, w: 34, h: 34, type: 'brick', hit: false, content: c[2], count: c[3]||0, oy:0}));

        const qCoords = [[685,292,'coin'], [901,292,'mushroom'], [987,292,'coin'], 
          [943,154,'coin'], [3342,292,'mushroom'], [4030,154,'coin'], [4544,292,'coin'], 
          [4672,292,'coin'], [4672,154,'mushroom'], [4800,292,'coin'], [5531,154,'coin'], 
          [7288,292,'coin']];
        
        qCoords.forEach(c => blocks.push({x: c[0], y: c[1]*0.8, w: 34, h: 34, type: 'qbox', hit: false, content: c[2], oy:0, timer:Math.random()*100}));

        const stairW = 34, stairH = 34;
        let sx = 5745;
        for(let i=0; i<4; i++) for(let j=0; j<=i; j++) blocks.push({x: sx+i*stairW, y: GROUND_HEIGHT-(j+1)*stairH, w: stairW, h: stairH, type: 'solid'});
        sx = 6001;
        for(let i=0; i<4; i++) for(let j=0; j<(4-i); j++) blocks.push({x: sx+i*stairW, y: GROUND_HEIGHT-(j+1)*stairH, w: stairW, h: stairH, type: 'solid'});

        flagpole = { x: 8505, y: 80, w: 4, h: GROUND_HEIGHT - 80, flagY: 80 };

        enemies = [680, 1380, 1720, 2870, 3680, 4450, 4930, 5080, 6780].map(ex => ({
          x: ex, y: GROUND_HEIGHT - 32, w: 32, h: 32, type: 'goomba', vx: -1, vy: 0, dead: 0, frame: 0
        }));

        particles = [];
      }

      function startGame() {
        if(state === 'PLAYING') return;
        state = 'PLAYING';
        if(lives <= 0) { lives = 3; score = 0; coins = 0; }
        time = 300; timeTimer = Date.now(); cameraX = 0;
        player.x = 50; player.y = 100; player.vx = 0; player.vy = 0; player.dead = false;
        player.isBig = false; player.height = 32;
        initLevel();
        if(!frameId) gameLoop();
      }

      function killPlayer() {
        if(player.dead) return;
        playSound('death');
        player.dead = true; player.vy = -10; player.vx = 0;
        state = 'DEAD'; deadTimer = 180; lives--;
      }

      function rectIntersect(r1, r2) {
        return !(r2.x > r1.x + r1.w || r2.x + r2.w < r1.x || r2.y > r1.y + r1.h || r2.y + r2.h < r1.y);
      }

      function update() {
        if(state === 'TITLE') return;
        
        if(state === 'COMPLETE') {
          player.vx = 0;
          if(player.y < GROUND_HEIGHT - player.height) player.vy += GRAVITY;
          else { player.vy = 0; player.y = GROUND_HEIGHT - player.height; }
          player.y += player.vy;
          if(flagpole.flagY < GROUND_HEIGHT - 32) flagpole.flagY += 3;
          completeTimer--;
          if(completeTimer <= 0) state = 'TITLE';
          return;
        }

        if(state === 'DEAD') {
          player.y += player.vy; player.vy += GRAVITY; deadTimer--;
          if(deadTimer <= 0) { if(lives > 0) startGame(); else state = 'TITLE'; }
          return;
        }

        if(Date.now() - timeTimer > 1000) { time--; timeTimer = Date.now(); }
        if(time <= 0) killPlayer();

        const maxSpeed = keys.run ? RUN_SPEED : WALK_SPEED;
        if(keys.left) { player.vx -= WALK_ACCEL; player.facing = -1; }
        else if(keys.right) { player.vx += WALK_ACCEL; player.facing = 1; }
        else { player.vx *= 0.8; if(Math.abs(player.vx) < 0.1) player.vx = 0; }
        
        player.vx = Math.max(-maxSpeed, Math.min(maxSpeed, player.vx));
        player.x += player.vx;
        if(player.x < cameraX) player.x = cameraX;

        let pRect = {x: player.x, y: player.y, w: player.width, h: player.height};
        
        const checkCols = (rect) => {
          let cols = [];
          grounds.forEach(g => { if(rectIntersect(rect, {x: g.x, y: GROUND_HEIGHT, w: g.w, h: 480})) cols.push({x:g.x, y:GROUND_HEIGHT, w:g.w, h:480}); });
          pipes.forEach(p => { if(rectIntersect(rect, p)) cols.push(p); });
          blocks.forEach(b => { if(rectIntersect(rect, b)) cols.push(b); });
          return cols;
        };
        // X-only collision: pipes and solid blocks (no grounds — ground is floor-only)
        const checkColsX = (rect) => {
          let cols = [];
          const r = {x: rect.x, y: rect.y + 2, w: rect.w, h: rect.h - 4}; // inset 2px top/bottom
          pipes.forEach(p => { if(rectIntersect(r, p)) cols.push(p); });
          blocks.forEach(b => { if(rectIntersect(r, b)) cols.push(b); });
          return cols;
        };

        let hitX = checkColsX(pRect);
        if(hitX.length > 0) {
          // Use the nearest obstacle in the direction of movement
          if(player.vx > 0) {
            let nearest = hitX.reduce((a,b) => a.x < b.x ? a : b);
            player.x = nearest.x - player.width;
          } else if(player.vx < 0) {
            let nearest = hitX.reduce((a,b) => (a.x+a.w) > (b.x+b.w) ? a : b);
            player.x = nearest.x + nearest.w;
          }
          player.vx = 0;
        }

        if(jumpHeld && player.onGround) { playSound('jump'); player.vy = keys.run ? FAST_JUMP_VEL : JUMP_VEL; player.onGround = false; }
        jumpHeld = false;

        let grav = GRAVITY;
        if(keys.jump && player.vy < 0) grav = JUMP_GRAVITY;
        player.vy += grav;
        if(player.vy > MAX_Y_VEL) player.vy = MAX_Y_VEL;
        
        player.y += player.vy;
        pRect.x = player.x; pRect.y = player.y;
        
        let hitY = checkCols(pRect);
        player.onGround = false;
        if(hitY.length > 0) {
          let h = hitY[0];
          if(player.vy > 0) {
            player.y = h.y - player.height; player.vy = 0; player.onGround = true;
          } else if(player.vy < 0) {
            player.y = h.y + h.h; player.vy = 0;
            let hitBlock = blocks.find(b => b === h);
            if(hitBlock && !hitBlock.hit) {
              hitBlock.oy = -10;
              if(hitBlock.type === 'qbox' || (hitBlock.type === 'brick' && hitBlock.content)) {
                hitBlock.hit = true;
                if(hitBlock.content === 'coin' || hitBlock.type === 'brick') {
                  score += 100; if(hitBlock.content === 'coin') { coins++; playSound('coin'); } particles.push({x: hitBlock.x+10, y: hitBlock.y, vy: -5, type: 'coin', life: 20});
                } else if(hitBlock.content === 'mushroom') {
                  particles.push({x: hitBlock.x, y: hitBlock.y-34, vx: 2, vy: 0, type: 'mushroom'});
                }
              } else if(hitBlock.type === 'brick' && player.isBig) {
                hitBlock.hit = true; 
                particles.push({x: hitBlock.x, y: hitBlock.y, vx: -2, vy: -5, type: 'debris', life: 40});
              }
            }
          }
        }

        if(player.y > 600) killPlayer();

        enemies.forEach(e => {
          if(e.x < cameraX - 100 || e.x > cameraX + 900) return;
          if(e.dead) { e.dead++; return; }
          e.vy += GRAVITY; e.x += e.vx; e.y += e.vy;
          let eHit = checkCols(e);
          if(eHit.length > 0) {
            let h = eHit[0];
            if(e.vy > 0 && e.y + e.h >= h.y && e.y < h.y) { e.y = h.y - e.h; e.vy = 0; }
            else if(e.vx !== 0) { e.vx *= -1; e.x += e.vx * 2; }
          }
          e.frame += 0.1;
          
          if(rectIntersect(pRect, e)) {
            if(player.vy > 0 && player.y + player.height < e.y + 20) {
              playSound('stomp');
              e.dead = 1; player.vy = JUMP_VEL/1.5; score += 100;
              particles.push({x: e.x, y: e.y, text: '100', life: 30, type: 'text'});
            } else if(!player.invulnTimer) {
              if(player.isBig) { player.isBig = false; player.height = 32; player.invulnTimer = 60; } 
              else killPlayer();
            }
          }
        });
        if(player.invulnTimer > 0) player.invulnTimer--;

        particles.forEach(p => {
          if(p.type === 'coin') { p.vy += GRAVITY; p.y += p.vy; p.life--; }
          else if(p.type === 'text') { p.y -= 1; p.life--; }
          else if(p.type === 'mushroom') {
            // X movement
            p.x += p.vx;
            let pHitX = checkColsX({x: p.x, y: p.y+2, w: 32, h: 28});
            if(pHitX.length > 0) { p.vx *= -1; p.x += p.vx * 2; }
            // Y movement
            if(!p.onGround) p.vy += GRAVITY;
            p.y += p.vy;
            p.onGround = false;
            let pHit = checkCols({x: p.x, y: p.y, w: 32, h: 32});
            if(pHit.length > 0) {
              if(p.vy >= 0) { p.y = pHit[0].y - 32; p.vy = 0; p.onGround = true; }
              else { p.vy = 0; p.y = pHit[0].y + pHit[0].h; }
            }
            if(rectIntersect(pRect, {x: p.x, y: p.y, w: 32, h: 32})) {
              p.life = 0; score += 1000; playSound('mushroom');
              if(!player.isBig) { player.isBig = true; player.height = 64; player.y -= 32; }
            }
            if(p.x < cameraX - 200 || p.x > cameraX + 1000 || p.y > 600) p.life = 0;
          } else if(p.type === 'debris') {
            p.vy += GRAVITY * 0.5; p.x += p.vx; p.y += p.vy; p.life--;
          }
        });
        particles = particles.filter(p => p.life !== 0 && (p.life === undefined || p.life > 0));

        blocks.forEach(b => { if(b.oy < 0) b.oy += 1; if(b.timer!==undefined) b.timer++; });

        if(player.x > flagpole.x && state === 'PLAYING') {
          playSound('levelclear');
          state = 'COMPLETE'; completeTimer = 180; player.x = flagpole.x - 10;
        }

        if(player.x > cameraX + 400 && state !== 'DEAD') cameraX = player.x - 400;
        
        if(player.onGround) player.animFrame += Math.abs(player.vx)*0.1;
        else player.animFrame = 0;
      }

      function draw() {
        ctx.fillStyle = C.SKY; ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.imageSmoothingEnabled = false;
        
        ctx.save(); ctx.translate(-Math.floor(cameraX), 0);

        grounds.forEach(g => {
          ctx.fillStyle = C.DIRT; ctx.fillRect(g.x, GROUND_HEIGHT + 34, g.w, 480 - GROUND_HEIGHT - 34);
          for(let dx = g.x; dx < g.x + g.w; dx += 34) {
            let dw = Math.min(34, g.x + g.w - dx);
            drawSprite(sprTiles, 0, 16, 16 * (dw/34), 16, dx, GROUND_HEIGHT, dw, 34);
          }
        });

        pipes.forEach(p => {
          ctx.fillStyle = C.PIPE; ctx.fillRect(p.x+2, p.y+16, p.w-4, p.h-16); ctx.fillRect(p.x, p.y, p.w, 16);
          ctx.strokeStyle = C.PIPE_OUTLINE; ctx.strokeRect(p.x+2, p.y+16, p.w-4, p.h-16); ctx.strokeRect(p.x, p.y, p.w, 16);
        });

        if(flagpole) {
          ctx.fillStyle = '#fff'; ctx.fillRect(flagpole.x, flagpole.y, flagpole.w, flagpole.h);
          ctx.fillStyle = '#0f0'; ctx.fillRect(flagpole.x - 16, flagpole.flagY, 20, 20);
        }

        blocks.forEach(b => {
          if(b.type === 'brick' && b.hit && !b.content && b.count === 0 && b.oy === 0) return; // skip destroyed empty bricks
          ctx.save(); ctx.translate(b.x, b.y + b.oy);
          if(b.type === 'solid') {
            drawSprite(sprTiles, 16, 0, 16, 16, 0, 0, b.w, b.h);
          } else if(b.type === 'brick') {
            if(b.hit && (b.content || b.count > 0)) { drawSprite(sprTiles, 432, 0, 16, 16, 0, 0, b.w, b.h); }
            else { drawSprite(sprTiles, 16, 0, 16, 16, 0, 0, b.w, b.h); }
          } else if(b.type === 'qbox') {
            if(b.hit) { drawSprite(sprTiles, 432, 0, 16, 16, 0, 0, b.w, b.h); }
            else {
              let frame = Math.floor(b.timer/10)%3;
              drawSprite(sprTiles, 384 + frame*16, 0, 16, 16, 0, 0, b.w, b.h);
            }
          }
          ctx.restore();
        });

        particles.forEach(p => {
          if(p.type === 'coin') {
            let coinFrames = [52, 4, 20, 36];
            let cIdx = Math.floor(Date.now()/100) % 4;
            drawSprite(sprItems, coinFrames[cIdx], 113, 8, 14, p.x-4, p.y-7, 16, 14);
          } else if(p.type === 'text') {
            ctx.fillStyle = '#fff'; ctx.font = '16px "Courier New"'; ctx.fillText(p.text, p.x, p.y);
          } else if(p.type === 'mushroom') {
            drawSprite(sprItems, 0, 0, 16, 16, p.x, p.y, 32, 32);
          } else if(p.type === 'debris') {
            drawSprite(sprTiles, 16, 0, 16, 16, p.x, p.y, 10, 10);
          }
        });

        enemies.forEach(e => {
          if(e.dead > 20) return;
          if(e.dead) {
            drawSprite(sprEnemies, 61, 0, 16, 16, e.x, e.y+16, e.w, 16);
          } else {
            let exFrame = Math.floor(e.frame)%2===0 ? 0 : 30;
            drawSprite(sprEnemies, exFrame, 4, 16, 16, e.x, e.y, e.w, e.h);
          }
        });

        if(state !== 'TITLE' && (!player.invulnTimer || player.invulnTimer % 4 < 2)) {
          ctx.save();
          ctx.translate(player.x + player.width/2, player.y + player.height/2);
          ctx.scale(player.facing, 1);
          ctx.translate(-player.width/2, -player.height/2);
          
          if (player.dead) {
            drawSprite(sprMario, 160, 32, 15, 16, 0, 0, player.width, player.height);
          } else if (player.isBig) {
            if (!player.onGround) {
              drawSprite(sprMario, 144, 0, 16, 32, 0, 0, player.width, player.height);
            } else if (Math.abs(player.vx) > 0.1) {
              let f = Math.floor(player.animFrame) % 3;
              let wx = f === 0 ? 81 : f === 1 ? 97 : 113;
              let ww = f === 0 ? 16 : f === 1 ? 15 : 15;
              drawSprite(sprMario, wx, 0, ww, 32, 0, 0, player.width, player.height);
            } else {
              drawSprite(sprMario, 176, 0, 16, 32, 0, 0, player.width, player.height);
            }
          } else {
            if (!player.onGround) {
              drawSprite(sprMario, 144, 32, 16, 16, 0, 0, player.width, player.height);
            } else if (Math.abs(player.vx) > 0.1) {
              let f = Math.floor(player.animFrame) % 3;
              let wx = f === 0 ? 80 : f === 1 ? 96 : 112;
              let ww = f === 0 ? 15 : f === 1 ? 16 : 16;
              drawSprite(sprMario, wx, 32, ww, 16, 0, 0, player.width, player.height);
            } else {
              drawSprite(sprMario, 178, 32, 12, 16, 0, 0, player.width, player.height);
            }
          }
          ctx.restore();
        }

        ctx.restore();

        ctx.fillStyle = '#000'; ctx.fillRect(0, 0, canvas.width, 40);
        ctx.fillStyle = '#fff'; ctx.font = 'bold 18px "Courier New", monospace';
        ctx.fillText(`MARIO`, 40, 20); ctx.fillText(`${score.toString().padStart(6,'0')}`, 40, 36);
        ctx.fillText(`🪙 ×${coins.toString().padStart(2,'0')}`, 200, 36);
        ctx.fillText(`WORLD`, 360, 20); ctx.fillText(`1-1`, 370, 36);
        ctx.fillText(`TIME`, 520, 20); ctx.fillText(`${time}`, 525, 36);
        ctx.fillText(`LIVES: ${lives}`, 660, 36);

        if(state === 'TITLE') {
          ctx.fillStyle = 'rgba(0,0,0,0.7)'; ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.fillStyle = '#fff'; ctx.font = 'bold 48px "Courier New"';
          ctx.textAlign = 'center'; ctx.fillText('SUPER MARIO BROS', canvas.width/2, 200);
          ctx.font = '24px "Courier New"'; ctx.fillText('Press SPACE to Start', canvas.width/2, 260);
          ctx.textAlign = 'left';
        } else if(state === 'COMPLETE') {
          ctx.fillStyle = '#fff'; ctx.font = 'bold 36px "Courier New"';
          ctx.textAlign = 'center'; ctx.fillText('COURSE CLEAR!', canvas.width/2, 240);
          ctx.textAlign = 'left';
        }
      }

      function gameLoop() {
        update(); draw(); frameId = requestAnimationFrame(gameLoop);
      }

      startBtn.addEventListener('click', () => { initAudio(); startGame(); });
      
      draw();
    })();
    (function() {
      const VERCEL_ORIGIN = 'https://anxiangsir-github-io.vercel.app';
      const SCHOLAR_API = (window.location.hostname === 'localhost' ||
                           window.location.hostname.includes('vercel.app'))
        ? '/api/scholar'
        : VERCEL_ORIGIN + '/api/scholar';

      fetch(SCHOLAR_API)
        .then(r => r.json())
        .then(data => {
          if (data && data.citations) {
            const formatted = data.citations.toLocaleString() + '+';
            const el1 = document.getElementById('scholar-citations');
            const el2 = document.getElementById('scholar-citations-bio');
            if (el1) el1.textContent = formatted;
            if (el2) el2.textContent = formatted;
            const bioWrapper = document.getElementById('scholar-citations-bio-wrapper');
            if (bioWrapper) bioWrapper.style.display = '';
            const suffix = document.getElementById('scholar-citations-suffix');
            if (suffix) suffix.style.display = '';
          }
        })
        .catch(err => { console.warn('Scholar API unavailable:', err); });
    })();
    (function() {
      // Chat API endpoint — auto-detect environment
      // On Vercel or localhost the API is co-located; on GitHub Pages we
      // call the Vercel-hosted serverless function cross-origin.
      // ⚠️  Update this URL if the Vercel project is renamed or redeployed
      //     under a different domain (check Vercel Dashboard → Domains).
      const VERCEL_ORIGIN = 'https://anxiangsir-github-io.vercel.app';
      const CHAT_API_URL = (window.location.hostname === 'localhost' ||
                            window.location.hostname.includes('vercel.app'))
        ? '/api/chat'
        : VERCEL_ORIGIN + '/api/chat';
      
      // Chat log API for database storage
      const CHAT_LOG_API_URL = (window.location.hostname === 'localhost' ||
                                window.location.hostname.includes('vercel.app'))
        ? '/api/chat-log'
        : VERCEL_ORIGIN + '/api/chat-log';
      
      const chatMessages = document.getElementById('chatMessages');
      const chatInput = document.getElementById('chatInput');
      const chatSendBtn = document.getElementById('chatSendBtn');
      const chatContainer = document.querySelector('.chat-container');
      const chatFullscreenToggle = document.getElementById('chatFullscreenToggle');

      // Fullscreen toggle functionality
      let isFullscreen = false;
      let hasAutoFullscreened = false;

      function setChatFullscreen(enter) {
        isFullscreen = enter;
        if (enter) {
          chatContainer.classList.add('fullscreen');
          chatFullscreenToggle.textContent = '✕';
          chatFullscreenToggle.title = '退出全屏';
          document.body.style.overflow = 'hidden';
        } else {
          chatContainer.classList.remove('fullscreen');
          chatFullscreenToggle.textContent = '⛶';
          chatFullscreenToggle.title = '全屏';
          document.body.style.overflow = '';
        }
        chatMessages.scrollTop = chatMessages.scrollHeight;
      }

      chatFullscreenToggle.addEventListener('click', function() {
        setChatFullscreen(!isFullscreen);
      });

      document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && isFullscreen) {
          setChatFullscreen(false);
        }
      });

      // Maintain conversation history for context (capped to avoid excessive payloads)
      const conversationHistory = [];
      const MAX_HISTORY = 50;
      
      // Generate session ID for this conversation (UUID v4)
      let sessionId = null;
      try {
        // 尝试从 localStorage 读取现有 sessionId
        sessionId = localStorage.getItem('chatSessionId');
        if (!sessionId) {
          // 生成新的 UUID
          sessionId = crypto.randomUUID();
          localStorage.setItem('chatSessionId', sessionId);
        }
      } catch (e) {
        // 如果不支持 crypto.randomUUID 或 localStorage，使用简单的随机 ID
        sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
      }

      function addMessage(text, isUser) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${isUser ? 'user' : 'assistant'}`;
        
        const labelDiv = document.createElement('div');
        labelDiv.className = 'chat-message-label';
        labelDiv.textContent = isUser ? 'USER' : 'Xiang An';
        
        const contentDiv = document.createElement('div');
        if (isUser) {
          contentDiv.textContent = text;
        } else {
          contentDiv.className = 'chat-markdown';
          contentDiv.innerHTML = DOMPurify.sanitize(marked.parse(text));
        }
        
        messageDiv.appendChild(labelDiv);
        messageDiv.appendChild(contentDiv);
        chatMessages.appendChild(messageDiv);
        
        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
      }
      
      // 静默保存对话到数据库
      async function saveChatLog(role, content) {
        try {
          await fetch(CHAT_LOG_API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              session_id: sessionId,
              role: role,
              content: content,
              user_agent: navigator.userAgent
            })
          });
          // 静默成功，不做任何处理
        } catch (error) {
          // 静默失败，不影响聊天体验
          console.debug('Chat log save skipped:', error.message);
        }
      }

      async function callChatAPI(messages) {
        try {
          const response = await fetch(CHAT_API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages: messages })
          });
          const data = await response.json();
          return data.reply || '抱歉，服务暂时不可用。';
        } catch (error) {
          console.error('Chat API error:', error);
          return '抱歉，服务暂时不可用。';
        }
      }

      async function sendMessage() {
        const message = chatInput.value.trim();
        if (!message) return;
        
        // Auto-enter fullscreen on first message
        if (!hasAutoFullscreened) {
          hasAutoFullscreened = true;
          setChatFullscreen(true);
        }
        
        // Add user message to UI and history
        addMessage(message, true);
        conversationHistory.push({ role: 'user', content: message });
        chatInput.value = '';
        
        // 静默保存用户消息到数据库
        saveChatLog('user', message);
        
        // Disable button while waiting for response
        chatSendBtn.disabled = true;
        
        // Call the Python chat API with full conversation context
        const reply = await callChatAPI(conversationHistory);
        addMessage(reply, false);
        conversationHistory.push({ role: 'assistant', content: reply });
        if (conversationHistory.length > MAX_HISTORY) {
          conversationHistory.splice(0, conversationHistory.length - MAX_HISTORY);
        }
        
        // 静默保存助手回复到数据库
        saveChatLog('assistant', reply);
        
        chatSendBtn.disabled = false;
        chatInput.focus();
      }

      // Event listeners
      chatSendBtn.addEventListener('click', sendMessage);
      chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          sendMessage();
        }
      });
    })();
