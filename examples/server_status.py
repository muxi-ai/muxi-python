from muxi.server import ServerClient, ServerConfig


def main():
    client = ServerClient(
        ServerConfig(
            url="http://localhost:8000",
            key_id="<key_id>",
            secret_key="<secret_key>",
        )
    )
    print(client.status())


if __name__ == "__main__":
    main()
