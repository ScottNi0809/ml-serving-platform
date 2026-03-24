"""训练一个 Iris 分类器并保存为 .joblib 文件"""

import joblib
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from pathlib import Path

def main():
    # 1. 加载数据
    iris = load_iris()
    X_train, X_test, y_train, y_test = train_test_split(
        iris.data, iris.target, test_size=0.2, random_state=42
    )

    # 2. 训练模型
    model = LogisticRegression(max_iter=200, random_state=42)
    model.fit(X_train, y_train)

    # 3. 评估
    y_pred = model.predict(X_test)
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print(f"Classes: {iris.target_names.tolist()}")

    # 4. 保存模型
    output_dir = Path("scripts/models")
    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "iris_classifier.joblib"
    joblib.dump(model, model_path)
    print(f"Model saved to: {model_path}")

    # 5. 验证加载
    loaded = joblib.load(model_path)
    sample = X_test[:3]
    predictions = loaded.predict(sample)
    print(f"Sample predictions: {predictions}")
    print(f"Target names: {[iris.target_names[p] for p in predictions]}")

if __name__ == "__main__":
    main()