from muxi.formation import FormationClient, FormationConfig


def main():
    client = FormationClient(
        FormationConfig(server_url="http://localhost:8000", formation_id="<formation>", client_key="<client>", admin_key="<admin>")
    )
    print(client.health())


if __name__ == "__main__":
    main()
