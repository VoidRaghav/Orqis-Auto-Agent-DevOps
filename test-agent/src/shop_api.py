from payment import calculate_total


def main() -> None:
    total = calculate_total(100.0)
    print(f"Order total: {total}")


if __name__ == "__main__":
    main()
