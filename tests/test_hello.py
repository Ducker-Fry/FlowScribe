from flowscribe.engine.pipe_client import FlowScribeEngineClient


def main() -> None:
    client = FlowScribeEngineClient()

    if not client.connect():
        print("Connection failed")
        return

    try:
        result = client.send_hello()
        if result:
            print("Hello flow succeeded")
            print("Response:", result)
        else:
            print("Hello flow failed")
    finally:
        client.close()


if __name__ == "__main__":
    main()
