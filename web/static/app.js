// Cliente do Online Chess no navegador.
// Toda a regra do jogo roda no servidor Python (ChessEngine); aqui só desenhamos
// o tabuleiro igual à versão pygame e mandamos os cliques do jogador.

const width = 500, height = 500;
const dim = 8;
const sqsize = Math.floor(height / dim);
const images = {};

// cores do pygame: p.Color('white'), 'black', 'gray', 'dark gray', 'blue'
const COLORS = {
  white: "rgb(255,255,255)",
  black: "rgb(0,0,0)",
  gray: "rgb(190,190,190)",
  darkGray: "rgba(169,169,169,0.392)", // set_alpha(100)
  blue: "rgba(0,0,255,0.392)",
};

const $ = (id) => document.getElementById(id);

let me = null;
let ws = null;
let reconnectDelay = 500;
let view = null;

// estado da partida recebido do servidor
let game = null;
let sqSelected = null;
let playerClicks = [];
let waitingServer = false;
let lastMoveId = null;
let animation = null;

// ---------- utilidades ----------

function storage(fn) {
  try { return fn(window.sessionStorage); } catch { return null; }
}

function toast(text) {
  const el = $("toast");
  el.textContent = text;
  el.classList.remove("hidden");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.add("hidden"), 3000);
}

function show(name) {
  view = name;
  for (const v of ["authView", "lobbyView", "gameView"]) $(v).classList.toggle("hidden", v !== name);
  $("userBox").classList.toggle("hidden", !me);
  $("userName").textContent = me || "";
}

function el(tag, props = {}, children = []) {
  const node = Object.assign(document.createElement(tag), props);
  for (const child of children) node.append(child);
  return node;
}

// ---------- conta ----------

let registering = false;

function setAuthMode(isRegister) {
  registering = isRegister;
  $("authTitle").textContent = isRegister ? "Criar conta" : "Entrar";
  $("authSubmit").textContent = isRegister ? "Criar conta" : "Entrar";
  $("authSwitchText").textContent = isRegister ? "Já tem conta?" : "Não tem conta?";
  $("authSwitch").textContent = isRegister ? "Entrar" : "Criar conta";
  $("authPass").autocomplete = isRegister ? "new-password" : "current-password";
  $("authError").textContent = "";
}

$("authSwitch").onclick = () => setAuthMode(!registering);

$("authForm").onsubmit = async (e) => {
  e.preventDefault();
  $("authError").textContent = "";
  const res = await fetch(registering ? "/api/register" : "/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: $("authUser").value, password: $("authPass").value }),
  });
  const data = await res.json();
  if (!res.ok) {
    $("authError").textContent = data.error;
    return;
  }
  me = data.username;
  $("authPass").value = "";
  connect();
};

$("logoutBtn").onclick = async () => {
  await fetch("/api/logout", { method: "POST" });
  me = null;
  storage((s) => s.removeItem("chessRoom"));
  if (ws) { ws.onclose = null; ws.close(); ws = null; }
  setAuthMode(false);
  show("authView");
};

// ---------- WebSocket ----------

function send(data) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(data));
}

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => { reconnectDelay = 500; };
  ws.onmessage = (e) => handleMessage(JSON.parse(e.data));
  ws.onclose = (e) => {
    ws = null;
    if (e.code === 4001) { me = null; show("authView"); return; }
    toast("Conexão perdida, reconectando...");
    setTimeout(connect, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 2, 8000);
  };
}

function handleMessage(msg) {
  if (msg.type === "hello") {
    me = msg.username;
    // depois de recarregar a página volta para a sala em que estava
    const saved = storage((s) => JSON.parse(s.getItem("chessRoom") || "null"));
    if (saved) send({ type: "join", room: saved.room, role: saved.role });
    else show("lobbyView");
  } else if (msg.type === "rooms") {
    renderRooms(msg.rooms);
    if (view !== "gameView") show("lobbyView");
  } else if (msg.type === "state") {
    onState(msg);
  } else if (msg.type === "error") {
    waitingServer = false;
    toast(msg.message);
    if (view !== "gameView") {
      storage((s) => s.removeItem("chessRoom"));
      show("lobbyView");
    }
  }
}

// ---------- lobby ----------

const ROLE_LABEL = { white: "brancas", black: "pretas", spectator: "espectador" };
const STATUS_LABEL = {
  waiting: "Esperando jogador",
  playing: "Em andamento",
  checkmate: "Xeque-mate",
  stalemate: "Empate (afogamento)",
};

$("createForm").onsubmit = (e) => {
  e.preventDefault();
  send({ type: "create_room", name: $("roomName").value, role: $("roomRole").value });
  $("roomName").value = "";
};

function seatButton(room, color) {
  const holder = room[color];
  const mine = holder === me;
  const otherMine = room[color === "white" ? "black" : "white"] === me;
  const label = mine ? `Voltar (${ROLE_LABEL[color]})`
    : holder ? `${ROLE_LABEL[color]}: ${holder}`
    : `Jogar de ${ROLE_LABEL[color]}`;
  const btn = el("button", { textContent: label, className: holder ? "" : "primary" });
  btn.disabled = (holder && !mine) || otherMine;
  btn.onclick = () => send({ type: "join", room: room.id, role: color });
  return btn;
}

function renderRooms(rooms) {
  const list = $("roomList");
  list.replaceChildren();
  $("noRooms").classList.toggle("hidden", rooms.length > 0);
  for (const room of rooms) {
    const watch = el("button", { textContent: "Assistir" });
    watch.onclick = () => send({ type: "join", room: room.id, role: "spectator" });
    list.append(el("div", { className: "card room" }, [
      el("div", { className: "info" }, [
        el("span", { className: "name", textContent: room.name }),
        el("span", {
          className: "muted",
          textContent: `${STATUS_LABEL[room.status]} · criada por ${room.owner} · ${room.spectators} espectador(es)`,
        }),
      ]),
      el("div", { className: "buttons" }, [seatButton(room, "white"), seatButton(room, "black"), watch]),
    ]));
  }
}

// ---------- partida ----------

$("leaveBtn").onclick = () => {
  storage((s) => s.removeItem("chessRoom"));
  game = null;
  lastMoveId = null;
  send({ type: "leave" });
  show("lobbyView");
};

$("restartBtn").onclick = () => send({ type: "restart" });

function isPlayer() {
  return game && (game.role === "white" || game.role === "black");
}

function myTurn() {
  return game && game.room.status === "playing" &&
    game.role === (game.whiteToMove ? "white" : "black");
}

function onState(msg) {
  const isNewGame = !game || game.room.id !== msg.room.id;
  const moveId = msg.lastMove ? msg.lastMove.id : null;
  const animate = !isNewGame && moveId !== null && moveId !== lastMoveId;
  if (moveId !== lastMoveId) { sqSelected = null; playerClicks = []; }
  game = msg;
  lastMoveId = moveId;
  waitingServer = false;
  storage((s) => s.setItem("chessRoom", JSON.stringify({ room: msg.room.id, role: msg.role })));
  show("gameView");
  renderSide();
  if (animate) startAnimation(msg.lastMove);
}

function playerLine(color) {
  const name = game.room[color];
  const online = name && game.online[color];
  return [
    el("span", { className: "dot" + (online ? " on" : "") }),
    " ",
    name ? name + (name === me ? " (você)" : "") : "— vago —",
  ];
}

function renderSide() {
  const { room } = game;
  $("gameTitle").textContent = room.name;
  $("whiteName").replaceChildren(...playerLine("white"));
  $("blackName").replaceChildren(...playerLine("black"));

  let status;
  if (room.status === "waiting") status = "Esperando o outro jogador entrar...";
  else if (room.status === "checkmate") status = game.whiteToMove ? "Pretas venceram por xeque-mate" : "Brancas venceram por xeque-mate";
  else if (room.status === "stalemate") status = "Empate por afogamento";
  else if (myTurn()) status = "Sua vez!";
  else status = game.whiteToMove ? "Vez das brancas" : "Vez das pretas";
  if (game.role === "spectator") status += " (você está assistindo)";
  $("gameStatus").textContent = status;

  $("spectatorList").textContent = game.spectatorNames.length
    ? "Espectadores: " + game.spectatorNames.join(", ") : "";
  $("lastMove").textContent = game.lastMove ? "Último lance: " + game.lastMove.notation : "";
  $("restartBtn").classList.toggle("hidden",
    !(isPlayer() && (room.status === "checkmate" || room.status === "stalemate")));
}

// ---------- desenho (mesma lógica do ChessMain.py) ----------

const canvas = $("board");
const ctx = canvas.getContext("2d");

function setupCanvas() {
  // resolução interna maior em telas retina, mas as coordenadas continuam 500x500
  const dpr = window.devicePixelRatio || 1;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function loadImages() {
  const pieces = ["wP", "wR", "wN", "wB", "wQ", "wK", "bP", "bR", "bN", "bB", "bQ", "bK"];
  for (const piece of pieces) {
    const img = new Image();
    // os arquivos dos peões estão como wp.png/bp.png
    img.src = `/images/${piece[1] === "P" ? piece[0] + "p" : piece}.png`;
    images[piece] = img;
  }
}

function colours() {
  return [COLORS.white, isPlayer() ? COLORS.black : COLORS.gray];
}

function drawBoard() {
  const c2 = colours();
  ctx.fillStyle = COLORS.white;
  ctx.fillRect(0, 0, width, height); // screen.fill(p.Color("White"))
  for (let r = 0; r < dim; r++) {
    for (let c = 0; c < dim; c++) {
      ctx.fillStyle = c2[(r + c) % 2];
      ctx.fillRect(c * sqsize, r * sqsize, sqsize, sqsize);
    }
  }
}

function highlightSquares() {
  if (!sqSelected) return;
  const [r, c] = sqSelected;
  if (game.board[r][c][0] !== (game.whiteToMove ? "w" : "b")) return;
  ctx.fillStyle = COLORS.darkGray;
  ctx.fillRect(c * sqsize, r * sqsize, sqsize, sqsize);
  ctx.fillStyle = COLORS.blue;
  for (const [sr, sc, er, ec] of game.validMoves) {
    if (sr === r && sc === c) ctx.fillRect(ec * sqsize, er * sqsize, sqsize, sqsize);
  }
}

function drawPiece(piece, r, c) {
  const img = images[piece];
  if (img && img.complete) ctx.drawImage(img, c * sqsize, r * sqsize, sqsize, sqsize);
}

function drawPieces(board) {
  for (let r = 0; r < dim; r++) {
    for (let c = 0; c < dim; c++) {
      if (board[r][c] !== "--") drawPiece(board[r][c], r, c);
    }
  }
}

function drawText(text) {
  ctx.font = 'bold 21px Helvetica, Arial, sans-serif';
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = COLORS.black;
  ctx.fillText(text, width / 2, height / 2);
  ctx.fillStyle = "rgb(255,0,0)";
  ctx.fillText(text, width / 2 + 2, height / 2 + 2);
}

function startAnimation(move) {
  const dR = move.end[0] - move.start[0];
  const dC = move.end[1] - move.start[1];
  const framesPerSquare = 7;
  animation = { move, dR, dC, frame: 0, frameCount: (Math.abs(dR) + Math.abs(dC)) * framesPerSquare, last: 0 };
}

function drawAnimationFrame(now) {
  const a = animation;
  // clock.tick(60): avança no máximo um quadro a cada ~16ms
  if (now - a.last >= 1000 / 60) { a.frame++; a.last = now; }
  const t = a.frameCount ? a.frame / a.frameCount : 1;
  const r = a.move.start[0] + a.dR * t;
  const c = a.move.start[1] + a.dC * t;
  drawBoard();
  drawPieces(game.board);
  const [er, ec] = a.move.end;
  ctx.fillStyle = colours()[(er + ec) % 2];
  ctx.fillRect(ec * sqsize, er * sqsize, sqsize, sqsize);
  if (a.move.pieceCaptured !== "--") drawPiece(a.move.pieceCaptured, er, ec);
  drawPiece(a.move.pieceMoved, r, c);
  if (a.frame >= a.frameCount) animation = null;
}

function render(now) {
  requestAnimationFrame(render);
  if (view !== "gameView" || !game) return;
  if (animation) { drawAnimationFrame(now); return; }
  drawBoard();
  highlightSquares();
  drawPieces(game.board);
  if (game.room.status === "checkmate") {
    drawText(game.whiteToMove ? "O PRETO VENCEU POR CHECKMATE" : "O BRANCO VENCEU POR CHECKMATE");
  } else if (game.room.status === "stalemate") {
    drawText("stalemate");
  }
}

// ---------- cliques (mesma lógica do loop de eventos do ChessMain.py) ----------

canvas.addEventListener("click", (e) => {
  if (!myTurn() || waitingServer) return;
  const rect = canvas.getBoundingClientRect();
  const col = Math.floor((e.clientX - rect.left) * (width / rect.width) / sqsize);
  const row = Math.floor((e.clientY - rect.top) * (height / rect.height) / sqsize);
  if (row < 0 || row >= dim || col < 0 || col >= dim) return;

  if (sqSelected && sqSelected[0] === row && sqSelected[1] === col) {
    sqSelected = null;
    playerClicks = [];
  } else {
    sqSelected = [row, col];
    playerClicks.push(sqSelected);
  }

  if (playerClicks.length === 2) {
    const [[sr, sc], [er, ec]] = playerClicks;
    const valid = game.validMoves.some((m) => m[0] === sr && m[1] === sc && m[2] === er && m[3] === ec);
    if (valid) {
      send({ type: "move", start: [sr, sc], end: [er, ec] });
      waitingServer = true;
      sqSelected = null;
      playerClicks = [];
    } else {
      playerClicks = [sqSelected];
    }
  }
});

// ---------- início ----------

setupCanvas();
loadImages();
requestAnimationFrame(render);

fetch("/api/me").then((r) => r.json()).then((data) => {
  if (data.username) {
    me = data.username;
    connect();
  } else {
    setAuthMode(false);
    show("authView");
  }
});
