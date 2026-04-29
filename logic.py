import sqlite3
from datetime import datetime
from config import DATABASE 
import os
import shutil
import cv2
import numpy as np
from math import sqrt, ceil, floor

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

def create_collage(image_paths):
    """
    Membuat kolase dari daftar path gambar.
    Mengembalikan array numpy (gambar kolase).
    """
    images = []
    for path in image_paths:
        # Baca gambar, jika gagal (misal file tidak ada) bisa di-skip atau diisi placeholder
        img = cv2.imread(path)
        if img is not None:
            images.append(img)
        else:
            # Buat placeholder hitam agar layout kolase tetap rapi
            print(f"Peringatan: Gambar {path} tidak ditemukan, diisi placeholder hitam.")
            placeholder = np.zeros((100, 100, 3), dtype=np.uint8)  # ukuran sementara
            images.append(placeholder)

    if not images:
        return None  # Tidak ada gambar sama sekali

    num_images = len(images)
    # Tentukan jumlah kolom berdasarkan akar kuadrat
    num_cols = floor(sqrt(num_images))
    if num_cols == 0:
        num_cols = 1
    num_rows = ceil(num_images / num_cols)

    # Asumsikan semua gambar berukuran sama, ambil ukuran dari gambar pertama
    img_h, img_w = images[0].shape[:2]

    # Buat kanvas kolase
    collage = np.zeros((num_rows * img_h, num_cols * img_w, 3), dtype=np.uint8)

    # Tempel gambar satu per satu
    for i, img in enumerate(images):
        # Jika ukuran gambar berbeda, resize dulu agar seragam (opsional)
        if img.shape[:2] != (img_h, img_w):
            img = cv2.resize(img, (img_w, img_h))
        row = i // num_cols
        col = i % num_cols
        collage[row*img_h:(row+1)*img_h, col*img_w:(col+1)*img_w] = img

    return collage

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
        
    def get_winners_img(self, user_id):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute(''' 
        SELECT image FROM winners 
        INNER JOIN prizes ON 
        winners.prize_id = prizes.prize_id
        WHERE user_id = ?''', (user_id, ))
            return cur.fetchall()

if __name__ == '__main__':
    manager = DatabaseManager(DATABASE)
    manager.create_tables()
    prizes_img = os.listdir('img')
    data = [(x,) for x in prizes_img]
    manager.add_prize(data)