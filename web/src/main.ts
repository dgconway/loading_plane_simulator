const NUM_ROWS = 10;
const SEATS_PER_ROW = 2; // 0=window, 1=aisle

enum State {
    QUEUED = 0,
    WALKING,
    STORING,
    WAITING,
    SEATED
}

class Passenger {
    row: number;
    seat: number;
    state: State;
    aislePos: number;
    prog: number;
    timer: number;
    element: HTMLElement | null = null; // DOM reference

    constructor(row: number, seat: number) {
        this.row = row;
        this.seat = seat;
        this.state = State.QUEUED;
        this.aislePos = -1;
        this.prog = 0.0;
        this.timer = 0.0;
    }

    get visPos(): number {
        if (this.state === State.WALKING) return this.aislePos + this.prog;
        return this.aislePos;
    }
}

class Simulation {
    passengers: Passenger[] = [];
    queue: Passenger[] = [];
    aisle: Map<number, Passenger> = new Map();
    seats: Map<string, Passenger> = new Map();
    elapsed = 0.0;
    running = false;
    done = false;
    
    tMove = 1.0;
    tStore = 3.0;
    tPass = 2.0;
    speed = 1.0;

    setup(strategy: string) {
        const pool: Passenger[] = [];
        for (let r = 0; r < NUM_ROWS; r++) {
            for (let s = 0; s < SEATS_PER_ROW; s++) {
                pool.push(new Passenger(r, s));
            }
        }

        if (strategy === "random") {
            for (let i = pool.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [pool[i], pool[j]] = [pool[j], pool[i]];
            }
        } else if (strategy === "back_to_front") {
            pool.sort((a, b) => {
                if (a.row !== b.row) return b.row - a.row; // 9 -> 0
                return a.seat - b.seat; // window 0 first
            });
        } else if (strategy === "front_to_back") {
            pool.sort((a, b) => {
                if (a.row !== b.row) return a.row - b.row; // 0 -> 9
                return a.seat - b.seat;
            });
        } else if (strategy === "one_per_row") {
            pool.sort((a, b) => {
                if (a.seat !== b.seat) return a.seat - b.seat; // window seats first
                return b.row - a.row; // 9 -> 0
            });
        }

        this.passengers = pool;
        this.queue = [...pool];
        this.aisle.clear();
        this.seats.clear();
        this.elapsed = 0.0;
        this.done = false;
    }

    update(dt: number) {
        if (!this.running || this.done) return;
        
        const scaledDt = dt * this.speed;
        this.elapsed += scaledDt;

        const active = this.passengers
            .filter(p => [State.WALKING, State.STORING, State.WAITING].includes(p.state))
            .sort((a, b) => b.aislePos - a.aislePos); // Front-most first

        for (const p of active) {
            this.tickPassenger(p, scaledDt);
        }

        this.tryBoard();

        if (this.passengers.length > 0 && this.passengers.every(p => p.state === State.SEATED)) {
            this.done = true;
            this.running = false;
            console.log(`All seated in ${this.elapsed.toFixed(1)}s`);
        }
    }

    tickPassenger(p: Passenger, dt: number) {
        if (p.state === State.WALKING) {
            let nxt = p.aislePos + 1;
            
            let maxProg = Infinity;
            if (nxt > p.row) {
                maxProg = 0.0;
            } else if (this.aisle.has(nxt)) {
                const blocker = this.aisle.get(nxt)!;
                if (blocker.state === State.WALKING) {
                    maxProg = blocker.prog; 
                } else {
                    maxProg = 0.0;
                }
            }
            
            const proposedProg = p.prog + (dt / this.tMove);
            p.prog = Math.min(proposedProg, Math.max(p.prog, maxProg));
            
            while (p.prog >= 1.0) {
                this.aisle.delete(p.aislePos);
                p.aislePos = nxt;
                this.aisle.set(nxt, p);

                if (nxt === p.row) {
                    p.prog = 0.0;
                    p.state = State.STORING;
                    p.timer = this.tStore;
                    return;
                }

                p.prog -= 1.0;
                
                // Check next row now that we moved forward
                nxt = p.aislePos + 1;
                if (nxt > p.row) {
                    p.prog = 0.0;
                    return;
                } else if (this.aisle.has(nxt)) {
                    const blk = this.aisle.get(nxt)!;
                    if (blk.state === State.WALKING) {
                        if (p.prog > blk.prog) {
                            p.prog = blk.prog;
                        }
                    } else {
                        p.prog = 0.0;
                        return; // Blocked, cannot progress into the next cell at all
                    }
                }
            }
        } else if (p.state === State.STORING) {
            p.timer -= dt;
            if (p.timer <= 0) {
                const otherKey = `${p.row},${1 - p.seat}`;
                if (this.seats.has(otherKey)) {
                    p.state = State.WAITING;
                    p.timer = this.tPass;
                } else {
                    this.seatPassenger(p);
                }
            }
        } else if (p.state === State.WAITING) {
            p.timer -= dt;
            if (p.timer <= 0) {
                this.seatPassenger(p);
            }
        }
    }

    seatPassenger(p: Passenger) {
        p.state = State.SEATED;
        this.aisle.delete(p.aislePos);
        this.seats.set(`${p.row},${p.seat}`, p);
        if (p.element) {
            p.element.remove();
            p.element = null;
        }
    }

    tryBoard() {
        if (this.queue.length === 0) return;
        if (!this.aisle.has(-1)) {
            const p = this.queue.shift()!;
            p.state = State.WALKING;
            p.aislePos = -1;
            p.prog = 0.0;
            this.aisle.set(-1, p);
        }
    }
}

// ────────────────────────────────────────────────────────────
// UI bindings & Rendering
// ────────────────────────────────────────────────────────────

const sim = new Simulation();
let lastTime = performance.now();
let reqId: number | null = null;

// DOM Elements
const timeDisplay = document.getElementById("time-display")!;
const planeBody = document.getElementById("plane-body")!;
const queueDots = document.getElementById("queue-dots")!;
const queueTitle = document.getElementById("queue-title")!;

const btnStart = document.getElementById("btn-start") as HTMLButtonElement;
const btnReset = document.getElementById("btn-reset") as HTMLButtonElement;

// Inputs
const radiosStrategy = document.querySelectorAll<HTMLInputElement>('input[name="strategy"]');
const tMoveSlider = document.getElementById("t-move") as HTMLInputElement;
const tStoreSlider = document.getElementById("t-store") as HTMLInputElement;
const tPassSlider = document.getElementById("t-pass") as HTMLInputElement;
const moveVal = document.getElementById("move-val") as HTMLInputElement;
const storeVal = document.getElementById("store-val") as HTMLInputElement;
const passVal = document.getElementById("pass-val") as HTMLInputElement;
const speedBtns = document.querySelectorAll('.speed-btn');

// Rendering constants mapping directly to CSS dimensions
const ROW_H = 51; // 46 cell + 5 pad
const PLANE_Y = 50; 
const WSEAT_X = 20; 
const ASEAT_X = 71; 
const AISLE_X = 122; 
const AISLE_W = 46; 
const CELL_CENTER = 46 / 2;

function buildGrid() {
    // Add entrance slot explicitly since Pygame had it. Wait, CSS has .entrance-slot
    const es = document.createElement("div");
    es.className = "entrance-slot";
    planeBody.appendChild(es);

    for (let r = 0; r < NUM_ROWS; r++) {
        const rowDiv = document.createElement("div");
        rowDiv.className = "grid-row";
        
        const labelDiv = document.createElement("div");
        labelDiv.className = "row-label";
        labelDiv.textContent = `R${r}${r===0?' ★':''}`;
        rowDiv.appendChild(labelDiv);

        const winSeat = document.createElement("div");
        winSeat.className = "seat-cell window";
        winSeat.id = `seat-${r}-0`;
        rowDiv.appendChild(winSeat);

        const aisleSeat = document.createElement("div");
        aisleSeat.className = "seat-cell aisle";
        aisleSeat.id = `seat-${r}-1`;
        rowDiv.appendChild(aisleSeat);

        const aislePath = document.createElement("div");
        aislePath.className = "aisle-cell";
        rowDiv.appendChild(aislePath);

        planeBody.appendChild(rowDiv);
    }
}

function updateFromSliders() {
    sim.tMove = parseFloat(tMoveSlider.value);
    sim.tStore = parseFloat(tStoreSlider.value);
    sim.tPass = parseFloat(tPassSlider.value);
    
    moveVal.value = sim.tMove.toFixed(1);
    storeVal.value = sim.tStore.toFixed(1);
    passVal.value = sim.tPass.toFixed(1);
}

function parseSafe(val: string, fallback: number): number {
    const p = parseFloat(val);
    return isNaN(p) ? fallback : p;
}

function updateFromInputs() {
    sim.tMove = Math.max(0.2, Math.min(5.0, parseSafe(moveVal.value, 1.0)));
    sim.tStore = Math.max(0.0, Math.min(10.0, parseSafe(storeVal.value, 3.0)));
    sim.tPass = Math.max(0.0, Math.min(5.0, parseSafe(passVal.value, 2.0)));

    tMoveSlider.value = sim.tMove.toString();
    tStoreSlider.value = sim.tStore.toString();
    tPassSlider.value = sim.tPass.toString();
}

[tMoveSlider, tStoreSlider, tPassSlider].forEach(el => {
    el.addEventListener('input', updateFromSliders);
});

[moveVal, storeVal, passVal].forEach(el => {
    el.addEventListener('input', updateFromInputs);
    // Ensure out-of-bounds typed values snap to the clamped limits the moment the user finishes typing (clicks away or hits enter)
    el.addEventListener('change', updateFromSliders);
});

speedBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        speedBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        sim.speed = parseInt(btn.getAttribute('data-speed') || "1");
    });
});

btnStart.addEventListener('click', () => {
    if (sim.running && !sim.done) return;
    
    let strategy = "random";
    radiosStrategy.forEach(r => { if (r.checked) strategy = r.value; });
    
    updateFromSliders();
    sim.setup(strategy);
    sim.running = true;
    lastTime = performance.now();
    clearBoardingDOM();
    renderQueue();
});

btnReset.addEventListener('click', () => {
    sim.running = false;
    sim.done = false;
    sim.elapsed = 0.0;
    sim.passengers = [];
    clearBoardingDOM();
    renderQueue();
    updateRender();
});

function clearBoardingDOM() {
    // Clear moving passengers
    document.querySelectorAll('.passenger').forEach(el => el.remove());
    // Clear seated colors
    document.querySelectorAll('.seat-cell.seated-passenger').forEach(el => {
        el.className = `seat-cell ${el.id.endsWith('0')?'window':'aisle'}`;
    });
}

function renderQueue() {
    queueDots.innerHTML = "";
    queueTitle.textContent = `Queue: ${sim.queue.length} waiting`;
    for (let i = 0; i < sim.queue.length; i++) {
        const dot = document.createElement("div");
        dot.className = "queue-dot";
        queueDots.appendChild(dot);
    }
}

function updateRender() {
    timeDisplay.textContent = sim.elapsed.toFixed(1) + "s";

    // Passengers in Aisle
    sim.passengers.forEach(p => {
        if ([State.WALKING, State.STORING, State.WAITING].includes(p.state)) {
            if (!p.element) {
                p.element = document.createElement("div");
                p.element.className = "passenger";
                p.element.textContent = p.row.toString();
                planeBody.appendChild(p.element);
            }
            
            // Map state to classes
            p.element.className = "passenger";
            if (p.state === State.WALKING) p.element.classList.add("walking");
            if (p.state === State.STORING) p.element.classList.add("storing");
            if (p.state === State.WAITING) p.element.classList.add("waiting");

            // Compute physics position
            // aisle is column index 2. left = 20(win) + 5 + 46(win) + 5 + 46(aisle_seat) + 5 = 127 ?
            // Let's rely on relative coordinates to planeBody:
            // planeBody padding top is 50px.
            // Row 0 is at top 50, row 1 is 50 + 51, etc.
            // Entrance is at visPos -1 => 50 - 51
            const vis = p.visPos;
            const py = 50 + (vis * ROW_H) + CELL_CENTER;
            const px = AISLE_X + CELL_CENTER; // 122 + 23 = 145

            p.element.style.transform = `translate(-50%, -50%) translate(${px}px, ${py}px)`;
        } else if (p.state === State.SEATED && !p.element) {
            // Already handled by seatPassenger logic which deletes element, we just colour the seat CSS
            const seatId = `seat-${p.row}-${p.seat}`;
            const s = document.getElementById(seatId);
            if (s && !s.classList.contains('seated-passenger')) {
                s.classList.add('seated-passenger');
            }
        }
    });

    renderQueue();
    
    if (sim.done) {
        timeDisplay.style.color = "var(--c-seated)";
    } else {
        timeDisplay.style.color = "var(--accent)";
    }
}

function loop(time: number) {
    const dtMs = time - lastTime;
    lastTime = time;

    // Cap dt in case tab is backgrounded
    const dt = Math.min(dtMs / 1000.0, 0.1); 

    if (sim.running && !sim.done) {
        sim.update(dt);
        updateRender();
    }

    reqId = requestAnimationFrame(loop);
}

// Init
buildGrid();
updateFromSliders();
renderQueue();
reqId = requestAnimationFrame(loop);
