import algo
import data


def main():
    itds = data.load_ITDs()
    noise = algo.sanitize(itds)

    for uid, itd in itds.items():
        print(f"For user {uid}")
        for t in itd.trajectories:
            tc = itd.count(t)
            nc = noise[uid][t]
            print(f"{str(t):<30}, tc = {tc}, nc = {nc}")


if __name__ == "__main__":
    main()
