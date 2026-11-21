"""python3.11 -m studio            run the web app on 127.0.0.1:4820
python3.11 -m studio token NAME   create an API token for an agent (printed once)
python3.11 -m studio password     set a new password (asked on the terminal)"""
import sys

from . import HOST, PORT


def main():
    args = sys.argv[1:]
    if args[:1] == ["token"] and len(args) == 2:
        from . import auth
        auth.ensure()
        print(auth.create_token(args[1]))
        return
    if args[:1] == ["password"]:
        import getpass
        from . import auth
        auth.ensure()
        pw = getpass.getpass("new password: ")
        auth.set_password(pw)
        print("password changed; restart the studio to sign every session out")
        return
    if args:
        sys.exit(__doc__)
    import uvicorn
    from . import auth
    auth.ensure()        # prints the generated password once, on first start
    uvicorn.run("studio.app:app", host=HOST, port=PORT, proxy_headers=False, log_level="info", access_log=False)


if __name__ == "__main__":
    main()
