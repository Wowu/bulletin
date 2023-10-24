from keras.datasets import mnist
from keras.models import Sequential
from keras.layers import Dense
from keras.optimizers import SGD
from keras.utils import to_categorical

def load_data():
    # Load the MNIST dataset
    (X_train, y_train), (X_test, y_test) = mnist.load_data()
    # Flatten and normalize input images
    X_train = X_train.reshape((X_train.shape[0], 28 * 28)) / 255.0
    X_test = X_test.reshape((X_test.shape[0], 28 * 28)) / 255.0
    # Convert the labels to one-hot encoding
    y_train = to_categorical(y_train)
    y_test = to_categorical(y_test)
    return X_train, y_train, X_test, y_test

def create_model():
    # Create a sequential model
    model = Sequential()
    # Add a fully connected layer
    model.add(Dense(128, activation='relu', input_shape=(28 * 28,)))
    # Add the output layer
    model.add(Dense(10, activation='softmax'))
    # Compile the model with SGD optimizer
    model.compile(optimizer=SGD(learning_rate=0.01), loss='categorical_crossentropy', metrics=['accuracy'])
    return model

X_train, y_train, X_test, y_test = load_data()

# import code; code.interact(local=dict(globals(), **locals()))

import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--workers', type=int, default=5)
parser.add_argument('--epochs', type=int, default=20)
args = parser.parse_args()

# CONFIG
workers = args.workers
epochs = args.epochs

batch_size = len(X_train) // workers

models = []
gradients = []

for rank in range(workers):
    model = create_model()
    models.append(model)
    gradients.append(model.get_weights())

for epoch in range(epochs):
    for rank in range(workers):
        start = rank * batch_size
        end = start + batch_size
        model = models[rank]

        # model.fit(X_train[start:end], y_train[start:end], epochs=1, batch_size=batch_size, verbose=0)

        # instead of fit we do this
        model.train_on_batch(X_train[start:end], y_train[start:end])

        gradient = model.get_weights()
        gradients[rank] = gradient

    # average gradients
    for i in range(len(gradients[0])):
        for j in range(1, len(gradients)):
            gradients[0][i] += gradients[j][i]
        gradients[0][i] /= len(gradients)

    # broadcast gradients
    for rank in range(workers):
        model = models[rank]
        model.set_weights(gradients[0])


# import code; code.interact(local=dict(globals(), **locals()))

# Train the model
# model.fit(X_train, y_train, epochs=1, batch_size=32, validation_data=(X_test, y_test))


# Evaluate the model
loss, acc = model.evaluate(X_test, y_test, verbose=0)
# print('Test loss:', loss)
# print('Test accuracy:', acc)
print(workers, epochs, loss, acc)
