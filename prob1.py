sum = 0
for i in range(0, 1001):
    if (i >= 3) and (i % 3 == 0):
        sum += i
    elif (i >=5) and (i % 5 == 0):
        sum += i

print(sum)