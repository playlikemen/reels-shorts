"""python3.11 -m studio            run the web app on 127.0.0.1:4820
python3.11 -m studio token NAME   create an API token for an agent (printed once)
python3.11 -m studio password     set a new password (asked on the terminal)
python3.11 -m studio mcp-key      store the MCP/API key from env STUDIO_MCP_KEY (only its scrypt hash is kept)
python3.11 -m studio mcp-key --revoke   remove the MCP/API key"""
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
    if args[:1] == ["mcp-key"]:
        import os
        from . import auth
        auth.ensure()
        if args[1:] == ["--revoke"]:
            print("MCP key revoked" if auth.revoke_key() else "no MCP key was set")
            return
        key = os.environ.get("STUDIO_MCP_KEY", "")
        if args[1:] or not key:
            sys.exit("set the key in the environment: STUDIO_MCP_KEY='...' python3.11 -m studio mcp-key")
        try:
            auth.set_key(key)
        except ValueError as e:
            sys.exit(str(e))
        print("MCP key stored (scrypt hash only). The running studio picks it up on the next request.")
        return
    if args:
        sys.exit(__doc__)
    import uvicorn
    from . import auth
    auth.ensure()        # prints the generated password once, on first start
    uvicorn.run("studio.app:app", host=HOST, port=PORT, proxy_headers=False, log_level="info", access_log=False)


if __name__ == "__main__":
    main()
