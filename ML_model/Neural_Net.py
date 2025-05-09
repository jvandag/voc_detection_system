import torch
import torch.nn as nn
import pandas as pd
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix
import numpy as np

# ==============================
# Load and Parse Sensor Data
# ==============================

file_path = "data/3-17_week_training.csv"
separate_test_file = True
tf_path = "data/3-17_week_training.csv" # Training file path
num_epochs = 10

label_mapping = { 'AIR': 0, 'LIGHT': 1, 'MEDIUM': 2, 'DARK': 3 }

# Load dataset
df = pd.read_csv(file_path, header=None)

# Extract labels (first column) and sensor values (every second column starting from column 2)
labels = df.iloc[:, 0]  # Labels (first column)
sensor_values = df.iloc[:, 2::2]  # Only sensor readings (columns 2,4,6,...)


# **Store Original Label Names Before Conversion**
if labels.dtype.name == 'object':
    #label_mapping = {name: i for i, name in enumerate(labels.astype('category').cat.categories)}  # Map words -> numbers
    reverse_mapping = {i: name for name, i in label_mapping.items()}  # Map numbers -> words
    labels = labels.map(label_mapping)  # Convert labels to numerical
else:
    label_mapping = None  # No mapping needed if labels were already numeric

# Normalize the sensor data (optional but often helpful)
scaler = StandardScaler()
sensor_values = scaler.fit_transform(sensor_values)

# Convert data to PyTorch tensors
sensor_tensor = torch.tensor(sensor_values, dtype=torch.float32)
labels_tensor = torch.tensor(labels.values, dtype=torch.long)

# Repeat the same process to create a test set from another file
if separate_test_file:
    # Load test dataset
    tf = pd.read_csv(tf_path, header=None)

    # Extract labels (first column) and sensor values (every second column starting from column 2)
    t_labels = tf.iloc[:, 0]  # Labels (first column)
    t_sensor_values = tf.iloc[:, 2::2]  # Only sensor readings (columns 2,4,6,...)


    # Store Original Label Names Before Conversion
    if t_labels.dtype.name == 'object':
        #t_label_mapping = {name: i for i, name in enumerate(t_labels.astype('category').cat.categories)}  # Map words -> numbers
        #t_reverse_mapping = {i: name for name, i in t_label_mapping.items()}  # Map numbers -> words
        t_reverse_mapping = {i: name for name, i in label_mapping.items()}  # Map numbers -> words
        t_labels = t_labels.map(label_mapping)  # Convert labels to numerical
    else:
        t_label_mapping = None  # No mapping needed if labels were already numeric

    # Normalize the sensor data (optional but often helpful)
    t_sensor_values = scaler.fit_transform(t_sensor_values)

    # Convert data to PyTorch tensors
    t_sensor_tensor = torch.tensor(t_sensor_values, dtype=torch.float32)
    t_labels_tensor = torch.tensor(t_labels.values, dtype=torch.long)
        
# ==============================
# Create Dataset
# ==============================

class SensorDataset(Dataset):
    def __init__(self, features, labels):
        self.features = features
        self.labels = labels

    def __len__(self):
        return len(self.features)

    def __getitem__(self, idx):
        return self.features[idx], self.labels[idx]

# Instead of using the entire dataset for training, let's split it (e.g., 80% train, 20% test)
dataset_size = len(sensor_tensor)
train_size = int(0.6 * dataset_size)
test_size = 0
if (separate_test_file):
    test_size = len(t_sensor_tensor)
    train_size = int(dataset_size)
else:
    test_size = dataset_size - train_size

# Create indices and split manually
indices = torch.randperm(dataset_size)
train_indices, test_indices = [], []
test_samples_per_class = 1
if not separate_test_file:
    test_samples_per_class = test_size // len(np.unique(labels))

for lbl in np.unique(labels):
    label_idxs = np.where(labels == lbl)[0]  # Get all indices for this label
    np.random.shuffle(label_idxs)  # Shuffle to randomize

    # determine number of test samples
    if separate_test_file:
        t_label_idxs = np.where(t_labels == lbl)[0]
        test_indices.extend(t_label_idxs)
        train_indices.extend(label_idxs)
    else:
        test_indices.extend(label_idxs[:test_samples_per_class])
        train_indices.extend(label_idxs[test_samples_per_class:])  # Use the rest for training

# Convert lists to PyTorch tensors
train_indices = torch.tensor(train_indices, dtype=torch.long)
test_indices = torch.tensor(test_indices, dtype=torch.long)

train_features = sensor_tensor[train_indices]
train_labels = labels_tensor[train_indices]
if (separate_test_file):
    test_features = t_sensor_tensor[test_indices]
    t_labels = t_labels_tensor[test_indices]
else:
    test_features = sensor_tensor[test_indices]
    t_labels = labels_tensor[test_indices]

# Create PyTorch datasets
train_dataset = SensorDataset(train_features, train_labels)
test_dataset = SensorDataset(test_features, t_labels)

batch_size = 8
train_loader = DataLoader(dataset=train_dataset, batch_size=batch_size, shuffle=True)
test_loader = DataLoader(dataset=test_dataset, batch_size=batch_size, shuffle=False)

# ==============================
# Define Neural Network
# ==============================

class NeuralNet(nn.Module):
    def __init__(self, input_size, hidden_size, num_classes):
        super(NeuralNet, self).__init__()
        self.l1 = nn.Linear(input_size, hidden_size)
        self.relu = nn.ReLU()
        self.l2 = nn.Linear(hidden_size, hidden_size // 2)  # Added extra hidden layer for complexity
        self.relu2 = nn.ReLU()
        self.l3 = nn.Linear(hidden_size // 2, num_classes)

    def forward(self, x):
        out = self.l1(x)
        out = self.relu(out)
        out = self.l2(out)
        out = self.relu2(out)
        out = self.l3(out)
        return out  # No softmax here, since CrossEntropyLoss applies it

# ==============================
# Initialize Model, Loss, and Optimizer
# ==============================

input_size = sensor_tensor.shape[1]  # 8 sensor values per row
hidden_size = 256  # Adjust as needed
num_classes = len(labels_tensor.unique())  # Should be 4 for your case
learning_rate = 0.001  # Lower learning rate is better for Adam

print('Using CUDA' if torch.cuda.is_available() else "Using CPU")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = NeuralNet(input_size, hidden_size, num_classes).to(device)

criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

# ==============================
# Train the Model
# ==============================

n_total_steps = len(train_loader)
for epoch in range(num_epochs):
    for i, (inputs, lbls) in enumerate(train_loader):
        inputs, lbls = inputs.to(device), lbls.to(device)

        # Forward pass
        outputs = model(inputs)
        loss = criterion(outputs, lbls)

        # Backward and optimization
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if (i + 1) % 10 == 0:
            print(f"Epoch [{epoch+1}/{num_epochs}], Step [{i+1}/{n_total_steps}], Loss: {loss.item():.4f}")

# ==============================
# Test the Model
# ==============================

all_preds = []
all_labels = []

with torch.no_grad():
    n_correct = 0
    n_samples = len(test_dataset)
    for i, (inputs, lbls) in enumerate(test_loader):
        inputs, lbls = inputs.to(device), lbls.to(device)
        outputs = model(inputs)
        _, predicted = torch.max(outputs, 1)
        n_correct += (predicted == lbls).sum().item()
    

        # Store predictions and labels for confusion matrix
        all_preds.extend(predicted.cpu().numpy())
        all_labels.extend(lbls.cpu().numpy())

    acc = n_correct / n_samples
    print(f"Overall Accuracy of the network on {n_samples} test samples: {100*acc:.2f} %")

# ==============================
# Convert Numerical Labels Back to Word Labels
# ==============================

# Convert predictions and labels back to word labels
if label_mapping is not None:
    all_preds_named = [reverse_mapping[p] for p in all_preds]  # Convert predictions
    all_labels_named = [reverse_mapping[l] for l in all_labels]  # Convert actual labels
else:
    all_preds_named = all_preds
    all_labels_named = all_labels
#print(all_labels_named)

from sklearn.metrics import ConfusionMatrixDisplay

# ==============================
# Confusion Matrix
# ==============================

# Ensure equal number of samples per label for visualization
equal_sample_idxs = []

for lbl in np.unique(all_labels):
    label_idxs = np.where(np.array(all_labels) == lbl)[0]  # Get indices for this label
    # Ensure we do not sample more than the available number of items
    if separate_test_file: 
        sample_size = len(label_idxs)
    else: 
        sample_size = min(test_samples_per_class, len(label_idxs))
    sampled_idxs = np.random.choice(label_idxs, sample_size, replace=False)
    equal_sample_idxs.extend(sampled_idxs)
    


all_preds_named = np.array(all_preds_named)
all_labels_named = np.array(all_labels_named)

equal_preds = all_preds_named[equal_sample_idxs]
equal_labels = all_labels_named[equal_sample_idxs]

# Ensure actual label names are correctly extracted
actual_label_names = list(reverse_mapping.values())  # Convert back to word labels

# Find misclassified indices
misclassified_idxs = np.where(equal_preds != equal_labels)[0]

# Print misclassified cases
print("\n=== Misclassified Points ===")
for idx in misclassified_idxs:
    original_idx = equal_sample_idxs[idx]  # Get original index from full test dataset
    true_label = equal_labels[idx]  # Actual class
    predicted_label = equal_preds[idx]  # Predicted class
    #print(f"Index: {original_idx}, True Label: {true_label}, Predicted: {predicted_label}")

# Print total number of misclassifications
print(f"\nTotal Misclassified Samples: {len(misclassified_idxs)} / {len(equal_labels)}")


# Generate confusion matrix
conf_matrix = confusion_matrix(equal_labels, equal_preds, labels=actual_label_names)

# Create and display confusion matrix
disp = ConfusionMatrixDisplay(confusion_matrix=conf_matrix, display_labels=actual_label_names)
fig, ax = plt.subplots(figsize=(7, 5))  # Set figure size
disp.plot(ax=ax, cmap="Blues", values_format="d")  # "d" ensures integer values are displayed

# Customize axis labels
ax.set_xlabel("Predicted Label")
ax.set_ylabel("True Label")
ax.set_title("Confusion Matrix")

plt.show()
# fig.savefig("confusion_matrix_4k.svg")
fig.savefig("confusion_matrix_4k.png", dpi=960)
...