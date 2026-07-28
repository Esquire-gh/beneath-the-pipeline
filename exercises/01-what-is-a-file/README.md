# 01 · What is a file, actually?

**Dependencies: none.** Shell and the Python standard library. Nothing to install.
macOS and Linux both work; on Windows use WSL.

Work in a scratch directory — you are about to create a file that claims to be a
gigabyte.

```sh
mkdir -p /tmp/floor && cd /tmp/floor
```

## 1 · The gap

```sh
printf 'abc' > three.txt

stat -x three.txt        # macOS
stat three.txt           # Linux

stat -f %k .             # macOS: block size of this filesystem
stat -f -c %s .          # Linux: same
```

Read the size. Read the blocks — they are counted in 512-byte units, so multiply by
512 to get bytes reserved. Name the gap.

## 2 · Append one character

```sh
printf 'd' >> three.txt
stat -x three.txt        # macOS  (stat three.txt on Linux)
```

The size moves. Watch whether the blocks do.

Keep appending until the reserved size changes. Where does it jump, and by how much?

## 3 · Two names, one file

```sh
ls -i three.txt
ln three.txt also-three.txt
ls -li three.txt also-three.txt
```

Both names show the same record number. Which one is "the" file?

## 4 · Delete one name

```sh
rm three.txt
cat also-three.txt
```

The bytes are still there. What did `rm` actually remove?

## 5 · A file that claims a gigabyte

```sh
truncate -s 1G big.img   # macOS without coreutils: mkfile -n 1g big.img
ls -l  big.img
du  -h big.img
```

`ls` reads a field in the record. `du` adds up blocks. They disagree by a gigabyte.

## 6 · The disk has no opinion about names

```sh
file icon.png
mv icon.png notes.txt
file notes.txt

head -c 8 notes.txt | xxd          # macOS and most Linux
head -c 8 notes.txt | hexdump -C   # if xxd is missing
```

`file` answers the same both times. It never read the name.

---

## Run it all, and record the numbers

The module page prints numbers from *your* machine. This script runs every command
above, shows the output, and writes `measurements.json`:

```sh
python exercises/01-what-is-a-file/investigate.py
```

Then check the observations reproduce:

```sh
python exercises/01-what-is-a-file/verify.py
```

## What you should be able to say afterwards

- Why three characters occupy a whole block, and what the two different "sizes" are.
- Where a file's name is stored, and why it is not in the file's own record.
- What `rm` removes, and when bytes actually become free.
- Why `file` and the `.png` extension are different kinds of evidence.
