import config


def main():
    from core import agent
    from core import master_agent

    print("Hello from wiki-json-to-llm-format!")
    # agent()
    master_agent()



if __name__ == "__main__":
    config.configure()
    main()
