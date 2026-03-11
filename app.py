from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import sqlite3
import json
import random
import os
from database import init_db, get_db

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-this-in-production'
socketio = SocketIO(app, cors_allowed_origins="*")

# Store waiting players and active games
waiting_players = []
active_games = {}

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('lobby'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        if not username:
            return render_template('login.html', error="Username required")
        
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        
        if not user:
            c = db.execute("INSERT INTO users (username) VALUES (?)", (username,))
            db.commit()
            user_id = c.lastrowid
        else:
            user_id = user['id']
        
        db.close()
        session['user_id'] = user_id
        session['username'] = username
        return redirect(url_for('lobby'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/lobby')
def lobby():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('lobby.html', username=session['username'])

# Socket.IO Events
@socketio.on('find_match')
def handle_find_match():
    user_id = session.get('user_id')
    username = session.get('username')
    sid = request.sid
    
    if not user_id:
        emit('error', {'message': 'Not logged in'})
        return
    
    # Remove if already waiting
    global waiting_players
    waiting_players = [p for p in waiting_players if p['user_id'] != user_id]
    
    # Check if already in game
    for game_id, game in active_games.items():
        if user_id in [game['player1_id'], game['player2_id']]:
            emit('error', {'message': 'Already in a game'})
            return
    
    # Add to waiting list
    waiting_players.append({
        'user_id': user_id,
        'username': username,
        'sid': sid
    })
    
    emit('waiting', {'message': 'Finding opponent...'})
    try_match()

def try_match():
    if len(waiting_players) >= 2:
        player1 = waiting_players.pop(0)
        player2 = waiting_players.pop(0)
        
        game_id = f"game_{player1['user_id']}_{player2['user_id']}_{random.randint(1000, 9999)}"
        
        # Get questions from DB
        db = get_db()
        questions = db.execute("SELECT * FROM questions ORDER BY RANDOM() LIMIT 5").fetchall()
        db.close()
        
        game_questions = []
        for q in questions:
            game_questions.append({
                'id': q['id'],
                'question': q['question'],
                'options': json.loads(q['options']),
                'correct_answer': q['correct_answer']
            })
        
        active_games[game_id] = {
            'game_id': game_id,
            'player1_id': player1['user_id'],
            'player2_id': player2['user_id'],
            'player1_name': player1['username'],
            'player2_name': player2['username'],
            'player1_sid': player1['sid'],
            'player2_sid': player2['sid'],
            'player1_score': 0,
            'player2_score': 0,
            'questions': game_questions,
            'current_question': 0,
            'player1_answers': {},
            'player2_answers': {},
            'status': 'starting'
        }
        
        socketio.emit('match_found', {
            'game_id': game_id,
            'opponent': player2['username'],
            'player_num': 1
        }, room=player1['sid'])
        
        socketio.emit('match_found', {
            'game_id': game_id,
            'opponent': player1['username'],
            'player_num': 2
        }, room=player2['sid'])

@socketio.on('join_game')
def handle_join_game(data):
    game_id = data.get('game_id')
    if game_id in active_games:
        join_room(game_id)
        emit('joined', {'game_id': game_id})

@socketio.on('player_ready')
def handle_player_ready(data):
    game_id = data.get('game_id')
    if game_id not in active_games:
        return
    
    game = active_games[game_id]
    if game['status'] == 'starting':
        game['status'] = 'playing'
        game['current_question'] = 0
        send_question(game_id)

def send_question(game_id):
    game = active_games[game_id]
    q_index = game['current_question']
    
    if q_index >= len(game['questions']):
        end_game(game_id)
        return
    
    question = game['questions'][q_index]
    
    socketio.emit('new_question', {
        'question_num': q_index + 1,
        'total_questions': len(game['questions']),
        'question': question['question'],
        'options': question['options'],
        'time_limit': 10
    }, room=game_id)
    
    socketio.start_background_task(question_timer, game_id, q_index)

def question_timer(game_id, expected_q_index):
    socketio.sleep(10)
    
    if game_id in active_games:
        game = active_games[game_id]
        if game['current_question'] == expected_q_index:
            socketio.emit('time_up', {
                'correct_answer': game['questions'][expected_q_index]['correct_answer']
            }, room=game_id)
            socketio.sleep(2)
            game['current_question'] += 1
            send_question(game_id)

@socketio.on('submit_answer')
def handle_submit_answer(data):
    game_id = data.get('game_id')
    answer = data.get('answer')
    time_left = data.get('time_left', 0)
    
    if game_id not in active_games:
        return
    
    game = active_games[game_id]
    user_id = session.get('user_id')
    q_index = game['current_question']
    
    if q_index >= len(game['questions']):
        return
    
    question = game['questions'][q_index]
    is_correct = (answer == question['correct_answer'])
    
    if user_id == game['player1_id']:
        game['player1_answers'][q_index] = {'answer': answer, 'correct': is_correct, 'time_left': time_left}
        if is_correct:
            game['player1_score'] += 1
    else:
        game['player2_answers'][q_index] = {'answer': answer, 'correct': is_correct, 'time_left': time_left}
        if is_correct:
            game['player2_score'] += 1
    
    p1_answered = q_index in game['player1_answers']
    p2_answered = q_index in game['player2_answers']
    
    if p1_answered and p2_answered:
        socketio.emit('question_result', {
            'correct_answer': question['correct_answer'],
            'player1_score': game['player1_score'],
            'player2_score': game['player2_score'],
            'player1_name': game['player1_name'],
            'player2_name': game['player2_name']
        }, room=game_id)
        
        socketio.sleep(2)
        game['current_question'] += 1
        send_question(game_id)

def end_game(game_id):
    game = active_games[game_id]
    
    winner_id = None
    winner_name = None
    
    if game['player1_score'] > game['player2_score']:
        winner_id = game['player1_id']
        winner_name = game['player1_name']
    elif game['player2_score'] > game['player1_score']:
        winner_id = game['player2_id']
        winner_name = game['player2_name']
    
    db = get_db()
    db.execute('''INSERT INTO games (player1_id, player2_id, player1_score, player2_score, winner_id) 
                  VALUES (?, ?, ?, ?, ?)''',
               (game['player1_id'], game['player2_id'], game['player1_score'], game['player2_score'], winner_id))
    db.commit()
    db.close()
    
    socketio.emit('game_over', {
        'player1_name': game['player1_name'],
        'player2_name': game['player2_name'],
        'player1_score': game['player1_score'],
        'player2_score': game['player2_score'],
        'winner': winner_name,
        'is_draw': winner_name is None
    }, room=game_id)
    
    del active_games[game_id]

@socketio.on('cancel_matchmaking')
def handle_cancel():
    user_id = session.get('user_id')
    global waiting_players
    waiting_players = [p for p in waiting_players if p['user_id'] != user_id]
    emit('matchmaking_cancelled')

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    global waiting_players
    waiting_players = [p for p in waiting_players if p['sid'] != sid]
    
    for game_id, game in list(active_games.items()):
        if game['player1_sid'] == sid or game['player2_sid'] == sid:
            socketio.emit('opponent_disconnected', room=game_id)
            del active_games[game_id]
            break

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)