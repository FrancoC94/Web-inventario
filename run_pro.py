from waitress import serve
from app import app

if __name__ == '__main__':
    print("-------------------------------------------")
    print("🚀 DRIVEFLOW PRO - MODO PRODUCCIÓN ACTIVO")
    print("📱 Acceso Global: http://100.93.158.13:5050")
    print("-------------------------------------------")
    serve(app, host='0.0.0.0', port=5050, threads=6)