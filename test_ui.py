import sys, locale
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from ui.main_window import MainWindow


class FakeClient:
    host = "http://example"; username = "u"; password = "p"
    def live_categories(self): return [{"category_id": "1", "category_name": "News"}]
    def vod_categories(self): return [{"category_id": "2", "category_name": "Action"}]
    def series_categories(self): return [{"category_id": "3", "category_name": "Drama"}]
    def live_streams(self, c): return [{"stream_id": 101, "name": "CNN"}, {"stream_id": 102, "name": "BBC"}]
    def vod_streams(self, c): return [{"stream_id": 201, "name": "The Movie", "container_extension": "mkv"}]
    def series(self, c): return [{"series_id": 301, "name": "Great Show"}]
    def series_info(self, s): return {"episodes": {"1": [{"id": 401, "title": "Pilot", "container_extension": "mp4"}]}}
    def live_url(self, i, ext="ts"): return f"http://example/live/{i}.ts"
    def movie_url(self, i, ext="mp4"): return f"http://example/movie/{i}.{ext}"
    def series_url(self, i, ext="mp4"): return f"http://example/series/{i}.{ext}"


app = QApplication(sys.argv)
locale.setlocale(locale.LC_NUMERIC, "C")
win = MainWindow({"name": "Test"}, FakeClient())
win.show()

results = []
def step1():
    results.append(("live categories", win.cat_list.count()))
    win.cat_list.setCurrentRow(0)
def step2():
    results.append(("live streams", win.content_list.count()))
    win._set_mode("series")
def step3():
    results.append(("series categories", win.cat_list.count()))
    win.cat_list.setCurrentRow(0)
def step4():
    results.append(("series list", win.content_list.count()))
    win._on_content_activated(win.content_list.item(0))  # open series -> episodes
def step5():
    results.append(("episodes (incl back)", win.content_list.count()))
    for label, n in results:
        print(f"  {label}: {n}")
    ok = (results[0][1] >= 1 and results[1][1] >= 2 and results[2][1] >= 1
          and results[3][1] >= 1 and results[4][1] >= 2)
    print("RESULT:", "PASS" if ok else "FAIL")
    win.player.shutdown()
    app.quit()

for i, fn in enumerate((step1, step2, step3, step4, step5), 1):
    QTimer.singleShot(i * 900, fn)
sys.exit(app.exec())
