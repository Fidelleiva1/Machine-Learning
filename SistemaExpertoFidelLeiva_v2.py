import mysql.connector
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from sklearn.neighbors import NearestNeighbors
import pandas as pd

# Conexión a MySQL
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="sistema_peliculas"
)
cursor = conn.cursor()

# Variable global para el usuario actual
usuario_actual = None

# Función para obtener valores únicos de una columna
def obtener_valores_unicos(columna):
    query = f"SELECT DISTINCT {columna} FROM peliculas"
    cursor.execute(query)
    return [row[0] for row in cursor.fetchall()]

# Función para obtener décadas en lugar de años individuales
def obtener_decadas():
    query = "SELECT DISTINCT año FROM peliculas ORDER BY año"
    cursor.execute(query)
    años = [row[0] for row in cursor.fetchall()]
    
    # Convertir años a décadas
    decadas = sorted(set(f"{(año // 10) * 10}s" for año in años))
    return decadas

# Función para convertir década seleccionada a rango de años
def obtener_rango_decada(decada):
    inicio = int(decada[:-1])
    fin = inicio + 9
    return inicio, fin

# Función para iniciar sesión
def iniciar_sesion():
    global usuario_actual
    usuario_actual = simpledialog.askstring("Inicio de Sesión", "Ingresa tu nombre:")
    if usuario_actual:
        mostrar_recomendaciones_previas()

# Función para mostrar recomendaciones previas
def mostrar_recomendaciones_previas():
    query = '''
    SELECT titulo, genero, duracion, estilo, popularidad, año, valoracion 
    FROM recomendaciones 
    WHERE usuario = %s AND valoracion IS NOT NULL
    ORDER BY fecha_recomendacion DESC
    '''
    cursor.execute(query, (usuario_actual,))
    recomendaciones = cursor.fetchall()
    
    if recomendaciones:
        recomendaciones_texto = "Tus recomendaciones anteriores:\n"
        for rec in recomendaciones:
            recomendaciones_texto += (f"{rec[0]} - {rec[1]}, {rec[2]} min, {rec[3]}, "
                                      f"{rec[4]}/10, Año: {rec[5]}, Valoración: {rec[6]}/5\n")
        messagebox.showinfo("Recomendaciones Anteriores", recomendaciones_texto)
    else:
        messagebox.showinfo("Bienvenido", "No tienes recomendaciones anteriores.")

# Función para obtener datos de películas
def obtener_datos_peliculas():
    query = '''
    SELECT titulo, genero, duracion, estilo, popularidad, año
    FROM peliculas
    '''
    cursor.execute(query)
    rows = cursor.fetchall()
    return pd.DataFrame(rows, columns=["titulo", "genero", "duracion", "estilo", "popularidad", "año"])

# Función para entrenar el modelo k-NN
def entrenar_modelo_knn(df):
    df_encoded = pd.get_dummies(df, columns=["genero", "estilo"])
    X = df_encoded.drop(columns=["titulo"])
    knn = NearestNeighbors(n_neighbors=5, metric='euclidean')
    knn.fit(X)
    return knn, df, X

# Función para recomendar una película usando k-NN
def recomendar_knn(genero, duracion, estilo, popularidad, decada):
    df = obtener_datos_peliculas()
    knn, df_encoded, X = entrenar_modelo_knn(df)
    
    # Convertir década a rango de años
    año_inicio, año_fin = obtener_rango_decada(decada)
    
    # Filtramos las películas que están dentro de la década seleccionada
    df_decada = df[(df["año"] >= año_inicio) & (df["año"] <= año_fin)]
    knn, df_encoded, X = entrenar_modelo_knn(df_decada)

    preferencias = pd.DataFrame([[genero, duracion, estilo, popularidad, (año_inicio + año_fin) // 2]], 
                                columns=["genero", "duracion", "estilo", "popularidad", "año"])
    preferencias_encoded = pd.get_dummies(preferencias, columns=["genero", "estilo"])
    preferencias_encoded = preferencias_encoded.reindex(columns=X.columns, fill_value=0)
    
    distancias, indices = knn.kneighbors(preferencias_encoded)
    recomendaciones = df_decada.iloc[indices[0]]
    
    recomendaciones_texto = "Te recomendamos ver:\n"
    for i, pelicula in recomendaciones.iterrows():
        recomendaciones_texto += (f"{pelicula['titulo']} - {pelicula['genero']}, {pelicula['duracion']} min, "
                                  f"{pelicula['estilo']}, {pelicula['popularidad']}/10, Año: {pelicula['año']}\n")
        guardar_recomendacion(usuario_actual, pelicula)
    return recomendaciones_texto

# Función para guardar recomendaciones en la base de datos
def guardar_recomendacion(usuario, pelicula):
    query = '''
    INSERT INTO recomendaciones (usuario, titulo, genero, duracion, estilo, popularidad, año)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    '''
    cursor.execute(query, (usuario, pelicula["titulo"], pelicula["genero"], pelicula["duracion"], 
                           pelicula["estilo"], pelicula["popularidad"], pelicula["año"]))
    conn.commit()

# Función para calificar una recomendación
def calificar_recomendacion():
    calificacion = simpledialog.askinteger("Valoración", "¿Qué tan buena fue la recomendación? (1-5)")
    if calificacion and 1 <= calificacion <= 5:
        query = '''
        UPDATE recomendaciones
        SET valoracion = %s
        WHERE usuario = %s AND valoracion IS NULL
        ORDER BY fecha_recomendacion DESC LIMIT 1
        '''
        cursor.execute(query, (calificacion, usuario_actual))
        conn.commit()
        messagebox.showinfo("Gracias", "Gracias por tu valoración.")

# Función para la recomendación k-NN desde la interfaz
def recomendar_pelicula_knn():
    genero = combo_genero.get()
    duracion = combo_duracion.get()
    estilo = combo_estilo.get()
    popularidad = int(combo_popularidad.get())
    decada = combo_decada.get()
    
    if not genero or not duracion or not estilo or not decada:
        messagebox.showwarning("Advertencia", "Por favor, selecciona todas las preferencias.")
        return

    duracion_minima, duracion_maxima = (0, 100) if duracion == "Corta" else (100, 500)
    duracion_media = (duracion_minima + duracion_maxima) // 2

    resultado_recomendacion = recomendar_knn(genero, duracion_media, estilo, popularidad, decada)
    resultado.set(resultado_recomendacion)
    calificar_recomendacion()

# Interfaz principal
ventana = tk.Tk()
ventana.title("Sistema de Recomendación de Películas")

btn_iniciar_sesion = tk.Button(ventana, text="Iniciar Sesión", command=iniciar_sesion)
btn_iniciar_sesion.grid(row=0, column=0, columnspan=2, pady=10)

tk.Label(ventana, text="Género").grid(row=1, column=0, padx=10, pady=10)
combo_genero = ttk.Combobox(ventana, values=obtener_valores_unicos("genero"))
combo_genero.grid(row=1, column=1)

tk.Label(ventana, text="Duración").grid(row=2, column=0, padx=10, pady=10)
combo_duracion = ttk.Combobox(ventana, values=["Corta", "Media", "Larga"])
combo_duracion.grid(row=2, column=1)

tk.Label(ventana, text="Estilo").grid(row=3, column=0, padx=10, pady=10)
combo_estilo = ttk.Combobox(ventana, values=obtener_valores_unicos("estilo"))
combo_estilo.grid(row=3, column=1)

tk.Label(ventana, text="Popularidad mínima").grid(row=4, column=0, padx=10, pady=10)
combo_popularidad = ttk.Combobox(ventana, values=[str(i) for i in range(7, 10)])
combo_popularidad.grid(row=4, column=1)

tk.Label(ventana, text="Década").grid(row=5, column=0, padx=10, pady=10)
combo_decada = ttk.Combobox(ventana, values=obtener_decadas())
combo_decada.grid(row=5, column=1)

btn_recomendar = tk.Button(ventana, text="Recomendar Película con k-NN", command=recomendar_pelicula_knn)
btn_recomendar.grid(row=6, column=0, columnspan=2, pady=20)

resultado = tk.StringVar()
label_resultado = tk.Label(ventana, textvariable=resultado, wraplength=300, justify="left")
label_resultado.grid(row=7, column=0, columnspan=2)

ventana.mainloop()
