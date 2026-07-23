import config


def main():
    from core import agent

    print("Hello from wiki-json-to-llm-format!")
    agent()



if __name__ == "__main__":
    config.configure()
    main()
