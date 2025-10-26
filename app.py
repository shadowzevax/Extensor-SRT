from flask import Flask, render_template, request, Response
from datetime import timedelta
import io
import os

# === SRT Processing Functions ===

def parse_time(t):
    """Convierte un string de tiempo SRT a timedelta"""
    try:
        h, m, s_ms = t.split(":")
        s, ms = s_ms.split(",")
        return timedelta(hours=int(h), minutes=int(m), seconds=int(s), milliseconds=int(ms))
    except ValueError:
        # Handle potential parsing errors gracefully
        print(f"Error parsing time: {t}")
        return timedelta() # Return zero timedelta on error

def format_time(td):
    """Convierte timedelta a formato SRT (hh:mm:ss,mmm)"""
    total_ms = int(td.total_seconds() * 1000)
    if total_ms < 0:
        total_ms = 0
    h = total_ms // 3600000
    m = (total_ms % 3600000) // 60000
    s = (total_ms % 60000) // 1000
    ms = total_ms % 1000
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def process_srt_content(srt_content, extender_ultimo_segundos=2):
    """
    Processes the SRT content to remove gaps between subtitles
    and optionally extend the last subtitle.
    """
    # Ensure consistent line endings and split into blocks
    content = srt_content.replace("\r\n", "\n").strip()
    bloques = [b.strip() for b in content.split("\n\n") if b.strip()]

    subs = []
    for bloque in bloques:
        lineas = bloque.split("\n")
        if len(lineas) >= 2 and "-->" in lineas[1]:
            idx = lineas[0].strip()
            try:
                t1_str, t2_str = lineas[1].split(" --> ")
                inicio = parse_time(t1_str.strip())
                fin = parse_time(t2_str.strip())
                texto = "\n".join(lineas[2:])
                subs.append({
                    "idx": idx,
                    "inicio": inicio,
                    "fin": fin,
                    "texto": texto.strip()
                })
            except ValueError as e:
                print(f"Skipping block due to parsing error: {bloque} - {e}")
                continue # Skip this block if time parsing fails

    # === Eliminar espacios entre subtítulos ===
    for i in range(len(subs) - 1):
        actual = subs[i]
        siguiente = subs[i + 1]
        # Forzar que el final del actual sea exactamente el inicio del siguiente
        actual["fin"] = siguiente["inicio"]

    # Extender el último subtítulo (opcional)
    if subs:
        subs[-1]["fin"] += timedelta(seconds=extender_ultimo_segundos)

    # === Construir el nuevo contenido SRT ===
    output_buffer = io.StringIO()
    for s in subs:
        output_buffer.write(f"{s['idx']}\n")
        output_buffer.write(f"{format_time(s['inicio'])} --> {format_time(s['fin'])}\n")
        output_buffer.write(f"{s['texto']}\n\n")

    return output_buffer.getvalue()

# === Flask App Setup ===
app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process-srt', methods=['POST'])
def process_srt():
    if 'srt_file' not in request.files:
        return "No file part in the request", 400

    file = request.files['srt_file']
    if file.filename == '':
        return "No selected file", 400

    if file and file.filename.endswith('.srt'):
        try:
            # Read file content with UTF-8 signature handling
            srt_content = file.read().decode('utf-8-sig')
            
            # Get output filename from form, default if not provided
            output_filename = request.form.get('output_filename', '').strip()
            if not output_filename:
                output_filename = "processed_subtitles.srt"
            elif not output_filename.endswith(".srt"):
                output_filename += ".srt"

            processed_content = process_srt_content(srt_content)

            return Response(
                processed_content,
                mimetype="text/srt",
                headers={"Content-disposition": f"attachment; filename={output_filename}"}
            )
        except Exception as e:
            print(f"An error occurred: {e}")
            return f"An error occurred during processing: {e}", 500
    else:
        return "Invalid file type. Please upload an .srt file.", 400

if __name__ == '__main__':
    # For development, run with debug=True. For production, use a proper WSGI server.
    # The default port is 5000.
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
