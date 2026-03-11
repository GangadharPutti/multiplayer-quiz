import sqlite3
import json

def init_db():
    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Questions table
    c.execute('''CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT NOT NULL,
        options TEXT NOT NULL,
        correct_answer INTEGER NOT NULL,
        category TEXT DEFAULT 'General'
    )''')
    
    # Games table
    c.execute('''CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player1_id INTEGER,
        player2_id INTEGER,
        player1_score INTEGER DEFAULT 0,
        player2_score INTEGER DEFAULT 0,
        winner_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (player1_id) REFERENCES users (id),
        FOREIGN KEY (player2_id) REFERENCES users (id),
        FOREIGN KEY (winner_id) REFERENCES users (id)
    )''')
    
    # Insert sample questions if none exist
    c.execute("SELECT COUNT(*) FROM questions")
    if c.fetchone()[0] == 0:
        sample_questions = [
            ("What is the capital of France?", json.dumps(["London", "Berlin", "Paris", "Madrid"]), 2, "Geography"),
            ("Which planet is known as the Red Planet?", json.dumps(["Venus", "Mars", "Jupiter", "Saturn"]), 1, "Science"),
            ("What is 2 + 2 × 2?", json.dumps(["6", "8", "4", "2"]), 0, "Math"),
            ("Who painted the Mona Lisa?", json.dumps(["Van Gogh", "Picasso", "Da Vinci", "Rembrandt"]), 2, "Art"),
            ("What is the largest ocean on Earth?", json.dumps(["Atlantic", "Indian", "Arctic", "Pacific"]), 3, "Geography")
        ]
        c.executemany("INSERT INTO questions (question, options, correct_answer, category) VALUES (?, ?, ?, ?)", sample_questions)
    
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect('quiz.db')
    conn.row_factory = sqlite3.Row
    return conn

if __name__ == '__main__':
    init_db()
    print("Database initialized!")