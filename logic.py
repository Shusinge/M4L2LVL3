import sqlite3
from datetime import datetime
from config import DATABASE 
import os
import shutil

def hide_img(img_name):
    """
    Memindahkan/menyalin gambar ke folder hidden_img
    """
    source = f'img/{img_name}'
    destination = f'hidden_img/{img_name}'
    
    try:
        os.makedirs('hidden_img', exist_ok=True)
        shutil.copy(source, destination)
        print(f"Gambar {img_name} berhasil disembunyikan")
    except FileNotFoundError:
        print(f"Gambar {img_name} tidak ditemukan di folder img/")
    except Exception as e:
        print(f"Error: {e}")

class DatabaseManager:
    def __init__(self, database):
        self.database = database

    def create_tables(self):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    user_name TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS prizes (
                    prize_id INTEGER PRIMARY KEY,
                    image TEXT,
                    used INTEGER DEFAULT 0
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS winners (
                    user_id INTEGER,
                    prize_id INTEGER,
                    win_time TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(user_id),
                    FOREIGN KEY(prize_id) REFERENCES prizes(prize_id)
                )
            ''')
            conn.commit()

    def add_user(self, user_id, user_name):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('INSERT OR IGNORE INTO users VALUES (?, ?)', (user_id, user_name))
            conn.commit()

    def add_prize(self, data):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.executemany('''INSERT INTO prizes (image) VALUES (?)''', data)
            conn.commit()

    def add_winner(self, user_id, prize_id):
        try:
            with sqlite3.connect(self.database) as conn:
                cur = conn.cursor()
                # Konversi ke int agar aman
                pid = int(prize_id)
                uid = int(user_id)

                # 1. Cek apakah user sudah menang hadiah ini
                cur.execute('SELECT * FROM winners WHERE user_id = ? AND prize_id = ?', (uid, pid))
                if cur.fetchone():
                    return False

                # 2. Cek batas pemenang (maksimal 3)
                cur.execute('SELECT COUNT(*) FROM winners WHERE prize_id = ?', (pid,))
                if cur.fetchone()[0] >= 3:
                    return False

                # 3. Cek apakah hadiah masih tersedia
                cur.execute('SELECT used FROM prizes WHERE prize_id = ?', (pid,))
                prize = cur.fetchone()
                if not prize or prize[0] == 1:
                    return False

                # 4. Tambah pemenang
                cur.execute('INSERT INTO winners (user_id, prize_id) VALUES (?, ?)', (uid, pid))
                return True
        except (sqlite3.Error, ValueError) as e:
            print(f"Database error: {e}")
            return False

    def mark_prize_used(self, prize_id):
        try:
            with sqlite3.connect(self.database) as conn:
                conn.execute('''UPDATE prizes SET used = 1 WHERE prize_id = ?''', (int(prize_id),))
                conn.commit()
        except (sqlite3.Error, ValueError) as e:
            print(f"Database error: {e}")

    def get_users(self):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor() 
            cur.execute("SELECT user_id FROM users")
            return [x[0] for x in cur.fetchall()]

    def get_prize_img(self, prize_id):
        try:
            with sqlite3.connect(self.database) as conn:
                cur = conn.cursor() 
                cur.execute("SELECT image FROM prizes WHERE prize_id = ?", (int(prize_id),))
                result = cur.fetchone()
                return result[0] if result else None
        except (sqlite3.Error, ValueError) as e:
            print(f"Database error: {e}")
            return None

    def get_random_prize(self):
        try:
            with sqlite3.connect(self.database) as conn:
                cur = conn.cursor()
                # Perbaikan: gunakan kolom 'image', bukan 'img'
                cur.execute('SELECT prize_id, image FROM prizes WHERE used = 0 ORDER BY RANDOM() LIMIT 1')
                result = cur.fetchone()
                return result if result else (None, None)
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return (None, None)

    def get_winners_count(self, prize_id):
        try:
            with sqlite3.connect(self.database) as conn:
                cur = conn.cursor()
                cur.execute('SELECT COUNT(*) FROM winners WHERE prize_id = ?', (int(prize_id),))
                result = cur.fetchone()
                return result[0] if result else 0
        except (sqlite3.Error, ValueError) as e:
            print(f"Database error: {e}")
            return 0

    def get_rating(self):
        try:
            with sqlite3.connect(self.database) as conn:
                cur = conn.cursor()
                # Perbaikan: kolom user_name, bukan username
                cur.execute('''
                    SELECT users.user_name, COUNT(*) as total_win
                    FROM users
                    INNER JOIN winners ON users.user_id = winners.user_id
                    GROUP BY users.user_id
                    ORDER BY total_win DESC
                    LIMIT 10
                ''')
                return cur.fetchall()
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []

if __name__ == '__main__':
    manager = DatabaseManager(DATABASE)
    manager.create_tables()
    prizes_img = os.listdir('img')
    data = [(x,) for x in prizes_img]
    manager.add_prize(data)