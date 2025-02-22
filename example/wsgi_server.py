from wsgiref.simple_server import make_server
from connecpy.wsgi import ConnecpyWSGIApp
from wsgi_service import HaberdasherService
from haberdasher_connecpy import HaberdasherServerSync


def main():
    # Create synchronous service instance
    service = HaberdasherService()

    # Create server with service implementation
    server = HaberdasherServerSync(service=service)
    print(f"Created server with prefix: {server._prefix}")

    # Create WSGI application and add service
    app = ConnecpyWSGIApp()
    app.add_service(server)

    # Start WSGI server
    with make_server("", 3000, app) as httpd:
        print("Serving on port 3000...")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")


if __name__ == "__main__":
    main()
