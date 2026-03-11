const socket = io();
let currentGame = null;
let timerInterval = null;
let selectedAnswer = null;

const matchmakingSection = document.getElementById('matchmaking');
const findBtn = document.getElementById('find-btn');
const waitingMsg = document.getElementById('waiting-msg');
const cancelBtn = document.getElementById('cancel-btn');
const gameContainer = document.getElementById('game-container');

findBtn.addEventListener('click', () => {
    socket.emit('find_match');
    findBtn.classList.add('hidden');
    waitingMsg.classList.remove('hidden');
});

cancelBtn.addEventListener('click', () => {
    socket.emit('cancel_matchmaking');
    waitingMsg.classList.add('hidden');
    findBtn.classList.remove('hidden');
});

socket.on('waiting', (data) => {
    console.log(data.message);
});

socket.on('match_found', (data) => {
    currentGame = data;
    waitingMsg.classList.add('hidden');
    matchmakingSection.classList.add('hidden');
    
    gameContainer.classList.remove('hidden');
    gameContainer.innerHTML = `
        <div class="game-container">
            <div class="game-header">
                <div class="player-card" id="player1-card">
                    <span class="player-name" id="p1-name">${data.player_num === 1 ? 'You' : data.opponent}</span>
                    <span class="player-score" id="p1-score">0</span>
                </div>
                <div class="vs">VS</div>
                <div class="player-card" id="player2-card">
                    <span class="player-name" id="p2-name">${data.player_num === 2 ? 'You' : data.opponent}</span>
                    <span class="player-score" id="p2-score">0</span>
                </div>
            </div>
            
            <div class="timer-container">
                <div class="timer-bar" id="timer-bar"></div>
                <span class="timer-text" id="timer-text">10</span>
            </div>
            
            <div class="question-container">
                <div class="question-num" id="question-num">Get Ready!</div>
                <h2 class="question-text" id="question-text">Game starting...</h2>
                <div class="options" id="options"></div>
            </div>
        </div>
    `;
    
    socket.emit('join_game', { game_id: data.game_id });
});

socket.on('joined', (data) => {
    socket.emit('player_ready', { game_id: currentGame.game_id });
});

socket.on('new_question', (data) => {
    selectedAnswer = null;
    const questionNum = document.getElementById('question-num');
    const questionText = document.getElementById('question-text');
    const optionsDiv = document.getElementById('options');
    const timerText = document.getElementById('timer-text');
    const timerBar = document.getElementById('timer-bar');
    
    questionNum.textContent = `Question ${data.question_num}/${data.total_questions}`;
    questionText.textContent = data.question;
    
    optionsDiv.innerHTML = '';
    data.options.forEach((opt, idx) => {
        const btn = document.createElement('button');
        btn.className = 'option';
        btn.textContent = opt;
        btn.onclick = () => selectAnswer(idx, btn);
        optionsDiv.appendChild(btn);
    });
    
    let timeLeft = data.time_limit;
    timerText.textContent = timeLeft;
    timerBar.style.width = '100%';
    
    clearInterval(timerInterval);
    timerInterval = setInterval(() => {
        timeLeft--;
        timerText.textContent = timeLeft;
        timerBar.style.width = `${(timeLeft / data.time_limit) * 100}%`;
        
        if (timeLeft <= 0) {
            clearInterval(timerInterval);
        }
    }, 1000);
});

function selectAnswer(index, btnElement) {
    if (selectedAnswer !== null) return;
    
    selectedAnswer = index;
    const options = document.querySelectorAll('.option');
    options.forEach(opt => opt.classList.add('disabled'));
    btnElement.classList.add('selected');
    
    const timerText = document.getElementById('timer-text');
    const timeLeft = parseInt(timerText.textContent);
    
    socket.emit('submit_answer', {
        game_id: currentGame.game_id,
        answer: index,
        time_left: timeLeft
    });
}

socket.on('time_up', (data) => {
    clearInterval(timerInterval);
    const options = document.querySelectorAll('.option');
    options.forEach((opt, idx) => {
        opt.classList.add('disabled');
        if (idx === data.correct_answer) {
            opt.classList.add('correct');
        }
    });
});

socket.on('question_result', (data) => {
    clearInterval(timerInterval);
    
    document.getElementById('p1-score').textContent = data.player1_score;
    document.getElementById('p2-score').textContent = data.player2_score;
    
    const options = document.querySelectorAll('.option');
    options.forEach((opt, idx) => {
        opt.classList.add('disabled');
        if (idx === data.correct_answer) {
            opt.classList.add('correct');
        } else if (opt.classList.contains('selected') && idx !== data.correct_answer) {
            opt.classList.add('wrong');
        }
    });
});

socket.on('game_over', (data) => {
    const isPlayer1 = currentGame.player_num === 1;
    const myScore = isPlayer1 ? data.player1_score : data.player2_score;
    const oppScore = isPlayer1 ? data.player2_score : data.player1_score;
    const myName = isPlayer1 ? data.player1_name : data.player2_name;
    const oppName = isPlayer1 ? data.player2_name : data.player1_name;
    
    let resultClass = 'draw';
    let resultText = "It's a Draw! 🤝";
    
    if (data.winner) {
        if (data.winner === myName) {
            resultClass = 'win';
            resultText = '🎉 You Won! 🎉';
        } else {
            resultClass = 'lose';
            resultText = '😔 You Lost';
        }
    }
    
    gameContainer.innerHTML = `
        <div class="result-container">
            <h1 id="result-title">Game Over!</h1>
            
            <div class="final-scores">
                <div class="final-player ${data.winner === myName ? 'winner' : ''}" id="final-p1">
                    <span class="name">${myName}</span>
                    <span class="score">${myScore}</span>
                </div>
                <div class="final-player ${data.winner === oppName ? 'winner' : ''}" id="final-p2">
                    <span class="name">${oppName}</span>
                    <span class="score">${oppScore}</span>
                </div>
            </div>
            
            <div class="result-message ${resultClass}" id="result-message">${resultText}</div>
            
            <button onclick="location.reload()" class="btn btn-primary">Play Again</button>
        </div>
    `;
});

socket.on('opponent_disconnected', () => {
    alert('Opponent disconnected!');
    location.reload();
});

socket.on('error', (data) => {
    alert(data.message);
    waitingMsg.classList.add('hidden');
    findBtn.classList.remove('hidden');
});