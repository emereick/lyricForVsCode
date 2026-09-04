import os
import sys
import time
import requests
import spotipy
from urllib.parse import quote
from spotipy.oauth2 import SpotifyOAuth
from concurrent.futures import ThreadPoolExecutor

# --- PENGATURAN ---
CLIENT_ID = '3a4b352b67354c048d0eefa10b617951'
CLIENT_SECRET = 'f95129e7bf5e435ea7bf2a623ecc2550'
REDIRECT_URI = 'https://google.com/'
SCOPE = 'user-read-currently-playing'

OFFSET_DETIK = 0.0 
AKTIFKAN_TERJEMAHAN = True  

# Warna Terminal ANSI
HIJAU = "\033[92m"
KUNING = "\033[93m"
ABU_ABU = "\033[90m"
RESET = "\033[0m"

CACHE_LIRIK = {}

def bersihkan_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')

def terjemahkan_teks(teks):
    if not teks.strip() or not AKTIFKAN_TERJEMAHAN:
        return teks
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=id&dt=t&q={quote(teks)}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            terjemahan = "".join([item[0] for item in data[0] if item[0]])
            return terjemahan if terjemahan else teks
    except Exception:
        pass
    return teks

def terjemahkan_banyak_paralel(daftar_teks):
    if not AKTIFKAN_TERJEMAHAN:
        return daftar_teks
    try:
        with ThreadPoolExecutor(max_workers=5) as executor:
            hasil = list(executor.map(terjemahkan_teks, daftar_teks))
        return hasil
    except Exception:
        return daftar_teks

def hubungkan_ke_spotify():
    auth_manager = SpotifyOAuth(client_id=CLIENT_ID,
                                client_secret=CLIENT_SECRET,
                                redirect_uri=REDIRECT_URI,
                                scope=SCOPE)
    return spotipy.Spotify(auth_manager=auth_manager)

def tarik_lirik_dari_lrclib(judul, artis):
    identifikasi = f"{artis} - {judul}".lower()
    if identifikasi in CACHE_LIRIK:
        return CACHE_LIRIK[identifikasi]

    url = "https://lrclib.net/api/search"
    params = {"q": f"{judul} {artis}"}
    headers = {"User-Agent": "SpotifyLiveLyrics/1.0 (https://github.com/)"}
    
    try:
        respon = requests.get(url, params=params, headers=headers, timeout=5)
        if respon.status_code == 200:
            hasil_pencarian = respon.json()
            if hasil_pencarian and len(hasil_pencarian) > 0:
                for item in hasil_pencarian:
                    if item.get("syncedLyrics"):
                        lirik = item.get("syncedLyrics")
                        CACHE_LIRIK[identifikasi] = lirik
                        return lirik
    except Exception:
        pass
    return None

def dapatkan_indeks_lirik_aktif(lirik_data, waktu_sekarang):
    idx_aktif = -1
    for i, (waktu_target, _, _) in enumerate(lirik_data):
        if waktu_sekarang >= waktu_target:
            idx_aktif = i
        else:
            break
    return idx_aktif

def jalankan_live_lirik():
    sp = hubungkan_ke_spotify()
    id_lagu_terakhir = None
    lirik_data = [] # Inisialisasi dari awal agar tidak UnboundLocalError
    
    bersihkan_terminal()
    print("=== Sistem Live Lirik Spotify Aktif ===")
    print("Menunggu lagu diputar...")

    while True:
        try:
            track = sp.current_user_playing_track()
        except Exception:
            time.sleep(2)
            continue
            
        if not track or not track['is_playing']:
            time.sleep(2)
            continue
            
        current_id = track['item']['id']
        judul_lagu = track['item']['name']
        artis = track['item']['artists'][0]['name']
        
        # Pemuatan Lirik Baru Saat Lagu Berganti
        if current_id != id_lagu_terakhir:
            id_lagu_terakhir = current_id
            lirik_data = [] # Kosongkan lirik data saat lagu ganti
            
            bersihkan_terminal()
            print(f"Memuat lirik untuk: {HIJAU}{judul_lagu}{RESET} oleh {artis}...")
            
            lirik_mentah = tarik_lirik_dari_lrclib(judul_lagu, artis)
            
            if not lirik_mentah:
                print(f"{ABU_ABU}Lirik tersinkronisasi tidak ditemukan. Menunggu lagu berikutnya...{RESET}")
                continue # Lompat ke pengulangan berikutnya

            waktu_list = []
            lirik_mentah_list = []
            
            for baris in lirik_mentah.split('\n'):
                baris = baris.strip()
                if baris.startswith('[') and ']' in baris:
                    try:
                        waktu_str, lirik = baris.split(']', 1)
                        waktu_bersih = waktu_str.strip('[]')
                        menit, detik = waktu_bersih.split(':')
                        total_detik = (int(menit) * 60) + float(detik) + OFFSET_DETIK
                        
                        waktu_list.append(total_detik)
                        lirik_mentah_list.append(lirik.strip())
                    except ValueError:
                        continue

            if AKTIFKAN_TERJEMAHAN:
                print("Menerjemahkan lirik...")
                lirik_indo_list = terjemahkan_banyak_paralel(lirik_mentah_list)
            else:
                lirik_indo_list = lirik_mentah_list

            lirik_data = list(zip(waktu_list, lirik_mentah_list, lirik_indo_list))

        # Jika lagu saat ini tidak memiliki lirik, jangan coba menyinkronkan
        if not lirik_data:
            time.sleep(3)
            continue 

        # Synchronize waktu lagu awal
        try:
            track = sp.current_user_playing_track()
            progress_ms = track['progress_ms'] if track else 0
        except Exception:
            progress_ms = 0

        waktu_mulai_lokal = time.time() - (progress_ms / 1000)
        indeks_terakhir_tampil = -99
        waktu_cek_terakhir = time.time()

        # Inner loop: Memutar animasi ketikan sinkron
        while True:
            waktu_sekarang = time.time() - waktu_mulai_lokal
            
            if time.time() - waktu_cek_terakhir > 1.5:
                waktu_cek_terakhir = time.time()
                try:
                    track_sync = sp.current_user_playing_track()
                except Exception:
                    track_sync = None
                
                if not track_sync or not track_sync['is_playing']:
                    print(f"\n{ABU_ABU}[Lagu dijeda]{RESET}")
                    while True:
                        time.sleep(2)
                        try:
                            t_check = sp.current_user_playing_track()
                            if t_check and t_check['is_playing']:
                                if t_check['item']['id'] != current_id:
                                    break
                                waktu_mulai_lokal = time.time() - (t_check['progress_ms'] / 1000)
                                break
                        except Exception:
                            pass
                    break 

                if track_sync['item']['id'] != current_id:
                    break

                progress_aktual = track_sync['progress_ms'] / 1000
                selisih = abs(waktu_sekarang - progress_aktual)
                
                if selisih > 1.0:
                    waktu_mulai_lokal = time.time() - progress_aktual
                    waktu_sekarang = progress_aktual
                    indeks_terakhir_tampil = -99  

            indeks_sekarang = dapatkan_indeks_lirik_aktif(lirik_data, waktu_sekarang)

            if indeks_sekarang != indeks_terakhir_tampil:
                bersihkan_terminal()
                print(f"=== Memutar: {HIJAU}{judul_lagu}{RESET} - {artis} ===\n")
                
                if indeks_sekarang >= 0:
                    if indeks_sekarang > 0:
                        print(f"{ABU_ABU}{lirik_data[indeks_sekarang-1][1]}{RESET}")
                        
                    _, teks_lirik, teks_indo = lirik_data[indeks_sekarang]
                    print(f"{HIJAU}➔ {teks_lirik}{RESET}")
                    if AKTIFKAN_TERJEMAHAN and teks_indo and teks_indo != teks_lirik:
                        print(f"{KUNING}   ↳ {teks_indo}{RESET}")
                    
                    if indeks_sekarang + 1 < len(lirik_data):
                        print(f"{ABU_ABU}{lirik_data[indeks_sekarang+1][1]}{RESET}")
                else:
                    print(f"{ABU_ABU}[Musik / Intro]{RESET}")
                    if len(lirik_data) > 0:
                        print(f"{ABU_ABU}Selanjutnya: {lirik_data[0][1]}{RESET}")

                indeks_terakhir_tampil = indeks_sekarang

            time.sleep(0.05)

        time.sleep(1)

if __name__ == '__main__':
    jalankan_live_lirik()
