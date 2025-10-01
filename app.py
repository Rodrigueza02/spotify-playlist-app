import os
from flask import Flask, render_template, redirect, request, session, url_for, jsonify
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = "super_secret_key"
app.config["SESSION_COOKIE_NAME"] = "spotify_session"

CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")

scope = "user-read-playback-state user-modify-playback-state user-read-currently-playing playlist-read-private playlist-read-collaborative user-library-read"

sp_oauth = SpotifyOAuth(client_id=CLIENT_ID,
                        client_secret=CLIENT_SECRET,
                        redirect_uri=REDIRECT_URI,
                        scope=scope)

# ----------------- TOKEN -----------------
def get_token():
    token_info = session.get("token_info", None)
    if not token_info:
        return None
    if sp_oauth.is_token_expired(token_info):
        token_info = sp_oauth.refresh_access_token(token_info["refresh_token"])
        session["token_info"] = token_info
    return token_info

def get_spotify():
    token_info = get_token()
    if not token_info:
        return None
    return Spotify(auth=token_info["access_token"])

# ----------------- RUTAS PRINCIPALES -----------------

@app.route("/")
def index():
    sp = get_spotify()
    if not sp:
        return redirect("/login")
    
    # Obtener lanzamientos recientes
    try:
        new_releases = sp.new_releases(limit=10, country='ES')
        lanzamientos = new_releases['albums']['items']
    except:
        lanzamientos = []
    
    return render_template("index.html", lanzamientos=lanzamientos)

# ----------------- FAVORITOS -----------------

@app.route("/toggle_favorito/<track_id>", methods=["POST"])
def toggle_favorito(track_id):
    sp = get_spotify()
    if not sp:
        return jsonify({"error": "No autenticado"}), 401
    
    if "favoritos" not in session:
        session["favoritos"] = []
    
    favoritos = session["favoritos"]
    
    if track_id in favoritos:
        favoritos.remove(track_id)
        estado = "removed"
    else:
        favoritos.append(track_id)
        estado = "added"
    
    session["favoritos"] = favoritos
    session.modified = True
    
    return jsonify({"status": estado})

@app.route("/favoritos")
def favoritos():
    sp = get_spotify()
    if not sp:
        return redirect("/login")

    favoritos_ids = session.get("favoritos", [])
    favoritos_list = []
    
    for track_id in favoritos_ids:
        try:
            track = sp.track(track_id)
            favoritos_list.append({
                "id": track["id"],
                "name": track["name"],
                "artist": ", ".join([a["name"] for a in track["artists"]]),
                "album": track["album"]["name"],
                "image": track["album"]["images"][0]["url"] if track["album"]["images"] else None
            })
        except Exception as e:
            print(f"Error obteniendo track {track_id}:", e)

    return render_template("favoritos.html", favoritos=favoritos_list)

# ----------------- PLAYLISTS -----------------

@app.route("/playlists")
def playlists():
    sp = get_spotify()
    if not sp:
        return redirect("/login")

    try:
        playlists_data = sp.current_user_playlists(limit=20)
        playlists = playlists_data["items"]
    except Exception as e:
        print("Error obteniendo playlists:", e)
        playlists = []

    return render_template("playlists.html", playlists=playlists)

@app.route("/playlist/<playlist_id>")
def playlist_detail(playlist_id):
    sp = get_spotify()
    if not sp:
        return redirect("/login")

    try:
        playlist = sp.playlist(playlist_id)
        tracks = playlist["tracks"]["items"]
    except Exception as e:
        print("Error obteniendo canciones:", e)
        playlist = {}
        tracks = []

    return render_template("playlist_detail.html", playlist=playlist, tracks=tracks)

# ----------------- REPRODUCCIÓN -----------------

@app.route("/play_track/<track_id>", methods=["POST"])
def play_track(track_id):
    sp = get_spotify()
    if not sp:
        return jsonify({"error": "No autenticado"}), 401
    try:
        sp.start_playback(uris=[f"spotify:track:{track_id}"])
        return ("", 204)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/current")
def current():
    sp = get_spotify()
    if not sp:
        return jsonify({
            "trackId": None,
            "trackTitle": "Nada reproduciéndose",
            "trackArtist": "",
            "albumTitle": "",
            "coverUrl": None,
            "duration": 0,
            "progress": 0
        })
    
    try:
        track = sp.currently_playing()
        if track and track.get("is_playing") and track.get("item"):
            item = track["item"]
            
            # Verificar si está en favoritos
            favoritos = session.get("favoritos", [])
            is_favorite = item["id"] in favoritos
            
            return jsonify({
                "trackId": item["id"],
                "trackTitle": item["name"],
                "trackArtist": ", ".join([artist["name"] for artist in item["artists"]]),
                "albumTitle": item["album"]["name"],
                "coverUrl": item["album"]["images"][0]["url"] if item["album"]["images"] else None,
                "duration": item["duration_ms"],
                "progress": track["progress_ms"],
                "isFavorite": is_favorite
            })
    except Exception as e:
        print("Error en /current:", e)
    
    return jsonify({
        "trackId": None,
        "trackTitle": "Nada reproduciéndose",
        "trackArtist": "",
        "albumTitle": "",
        "coverUrl": None,
        "duration": 0,
        "progress": 0,
        "isFavorite": False
    })

@app.route("/seek/<int:position_ms>", methods=["POST"])
def seek(position_ms):
    sp = get_spotify()
    if not sp:
        return jsonify({"error": "No autenticado"}), 401
    try:
        sp.seek_track(position_ms)
        return ("", 204)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/play")
def play_pause():
    sp = get_spotify()
    if not sp:
        return jsonify({"error": "No autenticado"}), 401
    try:
        playback = sp.current_playback()
        if playback and playback["is_playing"]:
            sp.pause_playback()
        else:
            sp.start_playback()
        return ("", 204)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/next")
def next_track():
    sp = get_spotify()
    if not sp:
        return jsonify({"error": "No autenticado"}), 401
    try:
        sp.next_track()
        return ("", 204)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/prev")
def prev_track():
    sp = get_spotify()
    if not sp:
        return jsonify({"error": "No autenticado"}), 401
    try:
        sp.previous_track()
        return ("", 204)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ----------------- LOGIN SPOTIFY -----------------

@app.route("/login")
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    token_info = sp_oauth.get_access_token(code)
    session["token_info"] = token_info
    return redirect(url_for("index"))

# ==================================================
# LISTA DOBLEMENTE ENLAZADA - PLAYLIST PERSONALIZADA
# ==================================================

import uuid

class Nodo:
    """Nodo de la lista doblemente enlazada"""
    def __init__(self, cancion):
        self.id = str(uuid.uuid4())
        self.cancion = cancion
        self.siguiente = None
        self.anterior = None
    
    def to_dict(self):
        return {
            "id": self.id,
            "titulo": self.cancion["titulo"],
            "artista": self.cancion["artista"],
            "duracion": self.cancion["duracion"],
            "album": self.cancion.get("album", "")
        }

class ListaDobleEnlazada:
    """Lista doblemente enlazada para playlist personalizada"""
    def __init__(self):
        self.cabeza = None
        self.cola = None
        self.actual = None
        self.tamanio = 0
    
    def esta_vacia(self):
        return self.cabeza is None
    
    def agregar_al_inicio(self, cancion):
        nuevo_nodo = Nodo(cancion)
        if self.esta_vacia():
            self.cabeza = nuevo_nodo
            self.cola = nuevo_nodo
            self.actual = nuevo_nodo
        else:
            nuevo_nodo.siguiente = self.cabeza
            self.cabeza.anterior = nuevo_nodo
            self.cabeza = nuevo_nodo
        self.tamanio += 1
        return nuevo_nodo.id
    
    def agregar_al_final(self, cancion):
        nuevo_nodo = Nodo(cancion)
        if self.esta_vacia():
            self.cabeza = nuevo_nodo
            self.cola = nuevo_nodo
            self.actual = nuevo_nodo
        else:
            nuevo_nodo.anterior = self.cola
            self.cola.siguiente = nuevo_nodo
            self.cola = nuevo_nodo
        self.tamanio += 1
        return nuevo_nodo.id
    
    def agregar_en_posicion(self, cancion, posicion):
        if posicion <= 0:
            return self.agregar_al_inicio(cancion)
        if posicion >= self.tamanio:
            return self.agregar_al_final(cancion)
        
        nuevo_nodo = Nodo(cancion)
        actual = self.cabeza
        for i in range(posicion):
            actual = actual.siguiente
        
        nuevo_nodo.anterior = actual.anterior
        nuevo_nodo.siguiente = actual
        actual.anterior.siguiente = nuevo_nodo
        actual.anterior = nuevo_nodo
        self.tamanio += 1
        return nuevo_nodo.id
    
    def eliminar_por_id(self, nodo_id):
        if self.esta_vacia():
            return False
        
        actual = self.cabeza
        while actual:
            if actual.id == nodo_id:
                if self.tamanio == 1:
                    self.cabeza = None
                    self.cola = None
                    self.actual = None
                elif actual == self.cabeza:
                    self.cabeza = actual.siguiente
                    self.cabeza.anterior = None
                    if self.actual == actual:
                        self.actual = self.cabeza
                elif actual == self.cola:
                    self.cola = actual.anterior
                    self.cola.siguiente = None
                    if self.actual == actual:
                        self.actual = self.cola
                else:
                    actual.anterior.siguiente = actual.siguiente
                    actual.siguiente.anterior = actual.anterior
                    if self.actual == actual:
                        self.actual = actual.siguiente
                
                self.tamanio -= 1
                return True
            actual = actual.siguiente
        return False
    
    def adelantar(self):
        if self.actual and self.actual.siguiente:
            self.actual = self.actual.siguiente
            return self.actual.to_dict()
        return None
    
    def retroceder(self):
        if self.actual and self.actual.anterior:
            self.actual = self.actual.anterior
            return self.actual.to_dict()
        return None
    
    def obtener_actual(self):
        if self.actual:
            return self.actual.to_dict()
        return None
    
    def obtener_todas(self):
        canciones = []
        actual = self.cabeza
        while actual:
            cancion_dict = actual.to_dict()
            cancion_dict["es_actual"] = (actual == self.actual)
            canciones.append(cancion_dict)
            actual = actual.siguiente
        return canciones
    
    def reproducir_por_id(self, nodo_id):
        actual = self.cabeza
        while actual:
            if actual.id == nodo_id:
                self.actual = actual
                return actual.to_dict()
            actual = actual.siguiente
        return None

# Instancia global de la playlist personalizada
mi_playlist = ListaDobleEnlazada()

# ========================================
# RUTAS PARA LA PLAYLIST PERSONALIZADA
# ========================================

@app.route("/mi_playlist")
def mi_playlist_page():
    return render_template("mi_playlist.html")

@app.route("/api/mi_playlist/canciones", methods=["GET"])
def obtener_mis_canciones():
    return jsonify({
        "canciones": mi_playlist.obtener_todas(),
        "tamanio": mi_playlist.tamanio
    })

@app.route("/api/mi_playlist/agregar", methods=["POST"])
def agregar_a_mi_playlist():
    data = request.json
    cancion = {
        "titulo": data.get("titulo"),
        "artista": data.get("artista"),
        "duracion": data.get("duracion", "3:30"),
        "album": data.get("album", "")
    }
    
    posicion = data.get("posicion", "final")
    
    if posicion == "inicio":
        nodo_id = mi_playlist.agregar_al_inicio(cancion)
    elif posicion == "final":
        nodo_id = mi_playlist.agregar_al_final(cancion)
    else:
        try:
            pos = int(posicion)
            nodo_id = mi_playlist.agregar_en_posicion(cancion, pos)
        except:
            nodo_id = mi_playlist.agregar_al_final(cancion)
    
    return jsonify({
        "success": True,
        "id": nodo_id,
        "canciones": mi_playlist.obtener_todas()
    })

@app.route("/api/mi_playlist/eliminar/<nodo_id>", methods=["DELETE"])
def eliminar_de_mi_playlist(nodo_id):
    success = mi_playlist.eliminar_por_id(nodo_id)
    return jsonify({
        "success": success,
        "canciones": mi_playlist.obtener_todas(),
        "actual": mi_playlist.obtener_actual()
    })

@app.route("/api/mi_playlist/reproducir/<nodo_id>", methods=["POST"])
def reproducir_de_mi_playlist(nodo_id):
    cancion = mi_playlist.reproducir_por_id(nodo_id)
    if cancion:
        return jsonify({
            "success": True,
            "cancion": cancion,
            "canciones": mi_playlist.obtener_todas()
        })
    return jsonify({"success": False}), 404

@app.route("/api/mi_playlist/adelantar", methods=["POST"])
def adelantar_mi_playlist():
    cancion = mi_playlist.adelantar()
    if cancion:
        return jsonify({
            "success": True,
            "cancion": cancion,
            "canciones": mi_playlist.obtener_todas()
        })
    return jsonify({"success": False, "message": "No hay siguiente canción"})

@app.route("/api/mi_playlist/retroceder", methods=["POST"])
def retroceder_mi_playlist():
    cancion = mi_playlist.retroceder()
    if cancion:
        return jsonify({
            "success": True,
            "cancion": cancion,
            "canciones": mi_playlist.obtener_todas()
        })
    return jsonify({"success": False, "message": "No hay canción anterior"})

@app.route("/api/mi_playlist/actual", methods=["GET"])
def obtener_actual_mi_playlist():
    cancion = mi_playlist.obtener_actual()
    if cancion:
        return jsonify(cancion)
    return jsonify({
        "titulo": "No hay canciones",
        "artista": "Agrega una canción para empezar",
        "duracion": "0:00"
    })
    
# ========================================
# RUTA PARA REPRODUCIR EN SPOTIFY DESDE MI PLAYLIST
# ========================================

@app.route("/api/mi_playlist/reproducir_spotify/<nodo_id>", methods=["POST"])
def reproducir_spotify_desde_mi_playlist(nodo_id):
    """Busca y reproduce en Spotify la canción de mi playlist"""
    # <CHANGE> Agregar get_spotify() que faltaba
    sp = get_spotify()
    if not sp:
        return jsonify({"success": False, "message": "No autenticado"}), 401
    
    try:
        # Obtener la canción de la lista doblemente enlazada
        cancion = mi_playlist.reproducir_por_id(nodo_id)
        
        if not cancion:
            return jsonify({"success": False, "message": "Canción no encontrada"}), 404
        
        # Buscar la canción en Spotify
        query = f"{cancion['titulo']} {cancion['artista']}"
        resultados = sp.search(q=query, type='track', limit=1)
        
        if not resultados['tracks']['items']:
            return jsonify({
                "success": False, 
                "message": f"No se encontró '{cancion['titulo']}' en Spotify"
            }), 404
        
        track = resultados['tracks']['items'][0]
        track_uri = track['uri']
        
        # Reproducir en Spotify
        try:
            sp.start_playback(uris=[track_uri])
            
            return jsonify({
                "success": True,
                "cancion": cancion,
                "spotify_track": {
                    "name": track['name'],
                    "artist": track['artists'][0]['name'],
                    "album": track['album']['name'],
                    "image": track['album']['images'][0]['url'] if track['album']['images'] else None,
                    "uri": track_uri
                },
                "canciones": mi_playlist.obtener_todas()
            })
            
        except Exception as playback_error:
            # Si no hay dispositivo activo, intentar transferir a uno disponible
            devices = sp.devices()
            if devices['devices']:
                sp.transfer_playback(devices['devices'][0]['id'], force_play=True)
                sp.start_playback(uris=[track_uri])
                
                return jsonify({
                    "success": True,
                    "cancion": cancion,
                    "spotify_track": {
                        "name": track['name'],
                        "artist": track['artists'][0]['name'],
                        "album": track['album']['name'],
                        "image": track['album']['images'][0]['url'] if track['album']['images'] else None,
                        "uri": track_uri
                    },
                    "canciones": mi_playlist.obtener_todas()
                })
            else:
                return jsonify({
                    "success": False,
                    "message": "No hay dispositivos de Spotify activos. Abre Spotify en tu dispositivo."
                }), 400
        
    except Exception as e:
        print(f"Error reproduciendo en Spotify: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Error: {str(e)}"
        }), 500
        
@app.route("/api/album/<album_id>/tracks")
def get_album_tracks(album_id):
    sp = get_spotify()
    if not sp:
        return jsonify({"error": "No autenticado"}), 401
    
    try:
        album = sp.album_tracks(album_id)
        tracks = [{"id": track["id"], "name": track["name"]} for track in album["items"]]
        return jsonify({"tracks": tracks})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
    
@app.route("/play_album/<album_id>", methods=["POST"])
def play_album(album_id):
    """Reproduce un álbum completo en Spotify"""
    sp = get_spotify()
    if not sp:
        return jsonify({"success": False, "message": "No autenticado"}), 401
    
    try:
        # Obtener las canciones del álbum
        album = sp.album_tracks(album_id)
        
        if not album['items']:
            return jsonify({"success": False, "message": "Álbum vacío"}), 404
        
        # Crear lista de URIs de las canciones
        track_uris = [f"spotify:track:{track['id']}" for track in album['items']]
        
        # Reproducir el álbum
        try:
            sp.start_playback(uris=track_uris)
            return jsonify({"success": True, "message": "Álbum reproducido"})
        except Exception as playback_error:
            devices = sp.devices()
            if devices['devices']:
                sp.transfer_playback(devices['devices'][0]['id'], force_play=True)
                sp.start_playback(uris=track_uris)
                return jsonify({"success": True, "message": "Álbum reproducido"})
            else:
                return jsonify({
                    "success": False,
                    "message": "No hay dispositivos de Spotify activos. Abre Spotify en tu dispositivo."
                }), 400
                
    except Exception as e:
        print(f"Error reproduciendo álbum: {str(e)}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500
    
    
# ----------------- MAIN -----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)