import numpy as np
from mpi4py import MPI
from tensorflow.keras.datasets import mnist
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense
from tensorflow.keras.utils import to_categorical

# Define MPI variables
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

# Load and preprocess MNIST data
(x_train, y_train), _ = mnist.load_data()
x_train = x_train.reshape(-1, 28 * 28) / 255.0
y_train = to_categorical(y_train, num_classes=10)

# Define neural network model
def create_model():
    model = Sequential()
    model.add(Dense(128, activation='relu', input_shape=(28 * 28,)))
    model.add(Dense(10, activation='softmax'))
    model.compile(loss='categorical_crossentropy', optimizer='adam', metrics=['accuracy'])
    return model

def sync_weights(model):
    weights = model.get_weights()

    for i in range(size):
        if i != rank:
            comm.Send(weights, dest=i, tag=0)
        else:
            for j in range(size):
                if j != rank:
                    comm.Recv(weights, source=j, tag=0)

    # Broadcast the updated weights to all workers
    comm.Bcast(weights, root=0)
    model.set_weights(weights)

# Main training loop
def train():
    print(0)
    model = create_model()
    print(0.1)
    sync_weights(model)
    print(0.2)

    print(1)

    batch_size = len(x_train) // size
    start = rank * batch_size
    end = start + batch_size

    print(2)

    for epoch in range(epochs):
        print(3)
        # Compute gradients
        model.fit(x_train[start:end], y_train[start:end], epochs=1, batch_size=batch_size, verbose=0)
        gradients = model.get_weights()

        # Average gradients across all workers
        comm.Barrier()
        for i in range(len(gradients)):
            gradients[i] /= size
            gradients[i] = comm.allreduce(gradients[i])

        # Update model weights
        model.set_weights(gradients)
        sync_weights(model)

    return model

if __name__ == '__main__':
    epochs = 2

    if rank == 0:
        print("Starting distributed training using MPI...")
        print("Number of workers:", size)

    model = train()

    if rank == 0:
        # Evaluate the final model on the test data or perform further tasks
        # test_loss, test_accuracy = model.evaluate(x_test, y_test)
        # print("Test Accuracy:", test_accuracy)
        print("Distributed training completed.")
