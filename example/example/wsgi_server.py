from wsgiref.simple_server import make_server

from .haberdasher_connecpy import HaberdasherWSGIApplication
from .wsgi_service import HaberdasherService


def main() -> None:
    # Create synchronous service instance
    service = HaberdasherService()

    # Create WSGI application and add service
    app = HaberdasherWSGIApplication(service)

    # Start WSGI server
    with make_server("", 3000, app) as httpd:
        print("Serving on port 3000...")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")


if __name__ == "__main__":
    main()
