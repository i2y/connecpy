from connecpy.wsgi import ConnecpyWSGIApp

import haberdasher_connecpy
from wsgi_service import HaberdasherService

service = haberdasher_connecpy.HaberdasherServerSync(service=HaberdasherService())
app = ConnecpyWSGIApp()
app.add_service(service)

if __name__ == "__main__":
    from wsgiref.simple_server import make_server

    with make_server("", 3000, app) as server:
        print("Serving on port 3000...")
        server.serve_forever()
