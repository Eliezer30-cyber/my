#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LM BLACK - Panel de Administración de Licencias
Servidor web para gestionar licencias (agregar, eliminar, ver)
"""

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime, timedelta
import secrets
import string

app = Flask(__name__)
CORS(app)

# Configuración
DATABASE = 'licenses.db'
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')  # Cambiar en producción

def init_db():
    """Inicializa la base de datos"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expiry_date TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            user_id TEXT,
            notes TEXT
        )
    ''')
    conn.commit()
    conn.close()

def generate_license_key(length=32):
    """Genera una clave de licencia aleatoria"""
    characters = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

def get_db_connection():
    """Obtiene una conexión a la base de datos"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    """Página principal del panel de administración"""
    return render_template('admin.html')

@app.route('/api/login', methods=['POST'])
def login():
    """Autenticación del administrador"""
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'Datos no proporcionados'}), 400
        
        password = data.get('password', '')
        
        if password == ADMIN_PASSWORD:
            return jsonify({'success': True, 'message': 'Login exitoso'})
        else:
            return jsonify({'success': False, 'message': 'Contraseña incorrecta'}), 401
    except Exception as e:
        print(f"Error en login: {e}")
        return jsonify({'success': False, 'message': f'Error del servidor: {str(e)}'}), 500

@app.route('/api/licenses', methods=['GET'])
def get_licenses():
    """Obtiene todas las licencias"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM licenses ORDER BY created_at DESC')
    licenses = cursor.fetchall()
    conn.close()
    
    result = []
    for license in licenses:
        result.append({
            'id': license['id'],
            'license_key': license['license_key'],
            'created_at': license['created_at'],
            'expiry_date': license['expiry_date'],
            'active': bool(license['active']),
            'user_id': license['user_id'],
            'notes': license['notes']
        })
    
    return jsonify(result)

@app.route('/api/licenses', methods=['POST'])
def add_license():
    """Agrega una nueva licencia"""
    data = request.json
    
    # Validar datos requeridos
    if not data.get('expiry_date'):
        return jsonify({'success': False, 'message': 'Fecha de expiración requerida'}), 400
    
    # Generar o usar clave proporcionada
    license_key = data.get('license_key')
    if not license_key:
        license_key = generate_license_key()
    
    expiry_date = data.get('expiry_date')
    user_id = data.get('user_id', '')
    notes = data.get('notes', '')
    active = data.get('active', True)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO licenses (license_key, expiry_date, active, user_id, notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (license_key, expiry_date, 1 if active else 0, user_id, notes))
        conn.commit()
        license_id = cursor.lastrowid
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Licencia agregada exitosamente',
            'license': {
                'id': license_id,
                'license_key': license_key,
                'expiry_date': expiry_date,
                'active': active,
                'user_id': user_id,
                'notes': notes
            }
        })
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'La clave de licencia ya existe'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/api/licenses/<int:license_id>', methods=['DELETE'])
def delete_license(license_id):
    """Elimina una licencia"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM licenses WHERE id = ?', (license_id,))
        conn.commit()
        deleted = cursor.rowcount
        conn.close()
        
        if deleted > 0:
            return jsonify({'success': True, 'message': 'Licencia eliminada exitosamente'})
        else:
            return jsonify({'success': False, 'message': 'Licencia no encontrada'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/api/licenses/<int:license_id>', methods=['PUT'])
def update_license(license_id):
    """Actualiza una licencia"""
    data = request.json
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Construir query dinámicamente
        updates = []
        values = []
        
        if 'expiry_date' in data:
            updates.append('expiry_date = ?')
            values.append(data['expiry_date'])
        
        if 'active' in data:
            updates.append('active = ?')
            values.append(1 if data['active'] else 0)
        
        if 'user_id' in data:
            updates.append('user_id = ?')
            values.append(data['user_id'])
        
        if 'notes' in data:
            updates.append('notes = ?')
            values.append(data['notes'])
        
        if not updates:
            return jsonify({'success': False, 'message': 'No hay campos para actualizar'}), 400
        
        values.append(license_id)
        query = f'UPDATE licenses SET {", ".join(updates)} WHERE id = ?'
        cursor.execute(query, values)
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Licencia actualizada exitosamente'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/api/verify-license', methods=['POST'])
def verify_license():
    """Verifica una licencia (endpoint usado por el cliente)"""
    data = request.json
    license_key = data.get('license_key')
    
    if not license_key:
        return jsonify({
            'valid': False,
            'message': 'Licencia no proporcionada'
        }), 200
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM licenses WHERE license_key = ?', (license_key,))
        license = cursor.fetchone()
        conn.close()
        
        if not license:
            return jsonify({
                'valid': False,
                'message': 'Licencia no encontrada'
            }), 200
        
        if not license['active']:
            return jsonify({
                'valid': False,
                'message': 'Licencia desactivada'
            }), 200
        
        # Verificar si está expirada
        expiry_date = datetime.fromisoformat(license['expiry_date'].replace('Z', '+00:00'))
        now = datetime.now(expiry_date.tzinfo) if expiry_date.tzinfo else datetime.now()
        
        if expiry_date < now:
            return jsonify({
                'valid': False,
                'message': 'Licencia expirada'
            }), 200
        
        # Licencia válida
        return jsonify({
            'valid': True,
            'expiry_date': license['expiry_date'],
            'message': 'Licencia válida'
        }), 200
    except Exception as e:
        return jsonify({
            'valid': False,
            'message': f'Error del servidor: {str(e)}'
        }), 500

if __name__ == '__main__':
    init_db()
    # Obtener puerto de variable de entorno (para Railway, Render, etc.)
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    print("=" * 50)
    print("Panel de Administración de Licencias - LM BLACK")
    print("=" * 50)
    if os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RENDER'):
        print(f"\nServidor desplegado en la nube")
        print(f"Puerto: {port}")
    else:
        print(f"\nAccede a: http://localhost:{port}")
    print(f"Contraseña por defecto: {ADMIN_PASSWORD}")
    print("\nPara cambiar la contraseña, establece la variable de entorno ADMIN_PASSWORD")
    print("=" * 50)
    app.run(debug=debug, host=host, port=port)

