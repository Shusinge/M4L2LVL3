import cv2
import discord
from discord.ext import commands, tasks
from logic import DatabaseManager, create_collage, hide_img
from config import TOKEN, DATABASE
import os

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

manager = DatabaseManager(DATABASE)
manager.create_tables()

# Perintah untuk user mendaftar
@bot.command()
async def start(ctx):
    user_id = ctx.author.id
    if user_id in manager.get_users():
        await ctx.send("Kamu sudah terdaftar!")
    else:
        manager.add_user(user_id, ctx.author.name)
        await ctx.send("""Hai! Selamat datang! Kamu telah berhasil terdaftar! Kamu akan menerima gambar baru setiap menit, dan kamu memiliki kesempatan untuk mendapatkannya! Untuk melakukannya, kamu perlu mengklik tombol 'Ambil!'! Hanya tiga pengguna pertama yang mengklik tombol 'Ambil!' yang akan mendapatkan gambarnya! =)""")

# Tugas terjadwal untuk mengirim gambar
@tasks.loop(minutes=1)
async def send_message():
    # Ambil SATU hadiah untuk dibagikan ke semua user
    prize = manager.get_random_prize()
    if not prize or prize[0] is None:
        print("Tidak ada hadiah tersedia")
        return
    
    prize_id, img = prize[0], prize[1]
    hide_img(img)
    
    # Kirim ke semua user
    for user_id in manager.get_users():
        try:
            user = await bot.fetch_user(user_id)
            if user:
                await send_image(user, f'hidden_img/{img}', prize_id)
        except discord.NotFound:
            print(f"User {user_id} tidak ditemukan")
        except discord.Forbidden:
            print(f"Tidak bisa mengirim DM ke user {user_id}")
    
    # Tandai hadiah sudah digunakan setelah dikirim ke semua
    manager.mark_prize_used(prize_id)

async def send_image(user, image_path, prize_id):
    with open(image_path, 'rb') as img:
        file = discord.File(img)
        button = discord.ui.Button(label="Ambil!", custom_id=str(prize_id))
        view = discord.ui.View()
        view.add_item(button)
        await user.send(file=file, view=view)

@bot.command()
async def rating(ctx):
    res = manager.get_rating()
    res = [f'| @{x[0]:<11} | {x[1]:<11}|\n{"_"*26}' for x in res]
    res = '\n'.join(res)
    res = f'|USER_NAME    |COUNT_PRIZE|\n{"_"*26}\n' + res
    await ctx.send(f"```\n{res}\n```")

@bot.command()
async def get_my_score(ctx):
    user_id = ctx.author.id

    # 1. Ambil daftar gambar yang sudah dimenangkan user
    winners_img = manager.get_winners_img(user_id)
    # winners_img sudah berupa list nama file, misal ['gambar1.png', 'gambar2.jpg']
    prizes_set = set(winners_img)  # Untuk pengecekan cepat

    # 2. Dapatkan SEMUA gambar yang ada di database (folder img)
    all_images = os.listdir('img')  # semua file gambar asli

    # 3. Buat list path gambar:
    #    - Jika user sudah menang -> pakai gambar asli dari img/
    #    - Jika belum -> pakai gambar tersembunyi (terenkripsi) dari hidden_img/
    image_paths = []
    for img_name in all_images:
        if img_name in prizes_set:
            image_paths.append(f'img/{img_name}')
        else:
            image_paths.append(f'hidden_img/{img_name}')

    # 4. Buat kolase
    collage = create_collage(image_paths)
    if collage is None:
        await ctx.send("Tidak ada gambar untuk ditampilkan.")
        return

    # 5. Simpan kolase ke file sementara
    output_path = f'collage_{user_id}.png'
    cv2.imwrite(output_path, collage)

    # 6. Kirim file ke Discord
    with open(output_path, 'rb') as f:
        file = discord.File(f)
        await ctx.send(file=file, content="🎨 **Kolase pencapaianmu** – Gambar yang sudah kamu dapatkan ditampilkan jelas, sisanya masih terenkripsi!")

    # 7. Hapus file sementara
    os.remove(output_path)

@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data['custom_id']
        user_id = interaction.user.id

        if manager.get_winners_count(custom_id) < 3:
            res = manager.add_winner(user_id, custom_id)
            if res:
                img = manager.get_prize_img(custom_id)
                with open(f'img/{img}', 'rb') as photo:
                    file = discord.File(photo)
                    await interaction.response.send_message(file=file, content="Selamat, kamu mendapatkan gambar!")
            else:
                await interaction.response.send_message(content="Kamu sudah mendapatkan gambar!", ephemeral=True)
        else:
            await interaction.response.send_message(content="Maaf, seseorang sudah mendapatkan gambar ini.", ephemeral=True)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')
    if not send_message.is_running():
        send_message.start()

bot.run(TOKEN)
