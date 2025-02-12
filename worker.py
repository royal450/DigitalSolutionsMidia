from celery import Celery

app = Celery("tasks", broker="redis://localhost:6379/0")

@app.task
def process_pdf_to_mp3(filename):
    # Same conversion logic here
    return "MP3 File Ready!"
