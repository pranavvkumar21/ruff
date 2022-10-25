import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.layers import Input,Dense
import tensorflow_probability as tfp
import numpy as np
import sys
np.set_printoptions(threshold=sys.maxsize)
import keras.backend as K
gamma= 0.992
lmbda = 0.95
critic_discount = 0.5
clipping_val = 0.2
entropy = 0.0025
tfd = tfp.distributions

act_optimizer = keras.optimizers.SGD(learning_rate=3.5e-4,clipnorm=1.0)
cri_optimizer = keras.optimizers.SGD(learning_rate=3.5e-4,clipnorm = 1.0)

def get_advantages(values, masks, rewards):
    returns = []
    gae = 0
    for i in reversed(range(len(rewards))):
        delta = rewards[i] + gamma * values[i + 1] * masks[i] - values[i]
        gae = delta + gamma * lmbda * masks[i] * gae
        returns.insert(0, gae + values[i])
    adv = np.array(returns).reshape((-1,1)) - np.array(values[:-1]).reshape((-1,1))
    adv = (adv - np.mean(adv)) / (np.std(adv) + 1e-10)
    return returns, adv

def ruff_train(actor,critic,states,logprobs,actions,returns,advantages,rewards):
    with tf.GradientTape(persistent = True) as tape:
        old_log_probs = logprobs
        mu,sigma = actor(states)

        dist = tfd.Normal(loc=mu, scale=sigma)
        new_log_probs = dist.log_prob(actions)
        ratio = K.exp(new_log_probs - old_log_probs)
        p1 = ratio * advantages
        p2 = K.clip(ratio, min_value=1 - clipping_val, max_value=1 + clipping_val) * advantages
        actor_loss = -K.mean(K.minimum(p1, p2),axis=1)
        critic_loss = K.abs(rewards - critic(states))
    actor_grads = tape.gradient(actor_loss, actor.trainable_variables)
    critic_grads = tape.gradient(critic_loss, critic.trainable_variables)
    act_optimizer.apply_gradients(zip(actor_grads, actor.trainable_variables))
    cri_optimizer.apply_gradients(zip(critic_grads, critic.trainable_variables))
    return actor_loss,critic_loss


def actor_Model(Input_shape,output_size,load=True):
    inputs = Input(shape=(Input_shape))
    X = Dense(256, activation="relu", name="fc1")(inputs)
    X = Dense(256, activation="relu", name="fc2")(X)
    mu = Dense(output_size, activation="tanh", name="mean")(X)
    sigma = Dense(output_size, activation="softplus", name="sigma")(X)
    model = keras.Model(inputs=inputs, outputs=[mu,sigma])
    if load:
        try:
            model.load_weights("../model/ppo_actor.h5")
            print("loaded actor weights")
        except:
            print("unable to load actor weights")
    return model

def critic_Model(Input_shape,output_size,load=True):
    inputs = Input(shape=(Input_shape))
    X = Dense(256, activation="relu")(inputs)
    X = Dense(256, activation="relu")(X)
    X = Dense(output_size)(X)
    model = keras.Model(inputs=inputs, outputs=X)
    if load:
        try:
            model.load_weights("../model/ppo_critic.h5")
            print("loaded critic weights")
        except:
            print("unable to load critic weights")
    return model

def save_model(actor,critic):
    actor.save_weights("../model/ppo_actor.h5")
    critic.save_weights("../model/ppo_critic.h5")
    print("model saved")
