from app import create_app, init_threads


app = create_app()


if __name__ == "__main__":
# init các thread / model / camera
    init_threads()
    app.run(host="0.0.0.0", port=5000, threaded=True, use_reloader=False, debug=False)