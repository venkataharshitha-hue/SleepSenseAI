import pandas as pd
import numpy as np
import pickle

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# =====================================
# Generate Training Dataset
# =====================================

np.random.seed(42)

rows = 1000

heart_rate = np.random.randint(55, 120, rows)

respiratory_rate = np.random.randint(10, 30, rows)

body_temperature = np.random.uniform(96, 102, rows)

blood_oxygen = np.random.randint(88, 100, rows)

sleep_hours = np.random.uniform(3, 10, rows)

emotional_state = np.random.randint(1, 11, rows)

lifestyle_score = np.random.randint(1, 11, rows)

# =====================================
# Stress Calculation Logic
# =====================================

stress_level = []

for i in range(rows):

    score = 0

    if heart_rate[i] > 90:
        score += 1

    if respiratory_rate[i] > 20:
        score += 1

    if body_temperature[i] > 99:
        score += 1

    if blood_oxygen[i] < 95:
        score += 1

    if sleep_hours[i] < 6:
        score += 1

    if emotional_state[i] > 7:
        score += 1

    if lifestyle_score[i] < 5:
        score += 1

    if score <= 2:
        stress_level.append("Low")

    elif score <= 4:
        stress_level.append("Moderate")

    else:
        stress_level.append("High")

# =====================================
# DataFrame
# =====================================

data = pd.DataFrame({

    "heart_rate": heart_rate,

    "respiratory_rate": respiratory_rate,

    "body_temperature": body_temperature,

    "blood_oxygen": blood_oxygen,

    "sleep_hours": sleep_hours,

    "emotional_state": emotional_state,

    "lifestyle_score": lifestyle_score,

    "stress_level": stress_level

})

# =====================================
# Features & Target
# =====================================

X = data.drop("stress_level", axis=1)

y = data["stress_level"]

# =====================================
# Train Test Split
# =====================================

X_train, X_test, y_train, y_test = train_test_split(

    X,
    y,

    test_size=0.2,

    random_state=42

)

# =====================================
# Model
# =====================================

model = RandomForestClassifier(

    n_estimators=200,

    max_depth=10,

    random_state=42

)

model.fit(X_train, y_train)

# =====================================
# Accuracy
# =====================================

predictions = model.predict(X_test)

accuracy = accuracy_score(

    y_test,
    predictions

)

print(
    f"Model Accuracy: {accuracy*100:.2f}%"
)

# =====================================
# Save Model
# =====================================

with open(
    "stress_model.pkl",
    "wb"
) as file:

    pickle.dump(
        model,
        file
    )

print(
    "Model Saved Successfully"
)
