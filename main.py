import logging
import config
from observability.logger import configure_logging


def main():
    from core import master_agent

    print("Hello from lite_harness!")
    # agent()
    master_agent()



if __name__ == "__main__":
    # level = getattr(logging, config.log_level.upper())
    # configure_logging(logging.DEBUG)
    configure_logging(logging.INFO)
    config.configure()
    main()
