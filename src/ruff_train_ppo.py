#!/usr/bin/env python3

from model_ppo import *
from ruff import *
import gc
import time
tfd = tfp.distributions
LOAD = False
NUM_EPISODES = 200_000
STEPS_PER_EPISODE = 1000
max_buffer = 30000
MINIBATCH_SIZE = 6000
ppo_epochs = 3
timestep =1.0/240.0
num_inputs = (60,)
n_actions = 16
gamma= 0.992
lmbda = 0.95
critic_discount = 0.5
clip_range = 0.2
entropy = 0.0025
kc = 0.0000002
kd = 0.999993
act_loss=0
crit_loss=0
max_reward = float("-inf")
req_step=0
bullet_file = "../model/test_ppo.bullet"
log_file = "../logs/ppo_ruff_logfile.csv"
reward_log = "../logs/ruff_reward_log.csv"
graph_count = 0
reward_list = ["forward_velocity","lateral_velocity","angular_velocity","Balance",
           "foot_stance", "foot_clear","foot_zvel", "frequency_err", "phase_err",
           "joint_constraints", "foot_slip", "policy_smooth","twist"]
n_actors = 10

class buffer:
    def __init__(self,max_len,batch_size):
        self.states = np.empty((0,60))
        self.rewards = np.empty((0,1))
        self.actions = np.empty((0,16))
        self.logprobs = np.empty((0,16))
        self.values = np.empty((0,1))
        self.advantages = np.empty((0,1))
        self.returns = np.empty((0,1))
        self.max_len = max_len
        self.keys = [i for i in range(max_len)]
        self.batch_size = batch_size

    def append(self,state=None,action=None,reward=None,value=None,logprobs=None,ret=None,adv=None):

        self.states = np.concatenate([self.states,state]) if type(state)!=type(None) else 0
        self.actions = np.concatenate([self.actions,action])
        self.rewards = np.concatenate([self.rewards,reward])
        self.values = np.concatenate([self.values,value])
        self.logprobs = np.concatenate([self.logprobs,logprobs])
        self.advantages = np.concatenate([self.advantages,adv])
        self.returns = np.concatenate([self.returns,ret])

        self.states = self.states[-self.max_len:]
        self.actions = self.actions[-self.max_len:]
        self.rewards = self.rewards[-self.max_len:]
        self.values = self.values[-self.max_len:]
        self.logprobs = self.logprobs[-self.max_len:]
        self.advantages = self.advantages[-self.max_len:]
        self.returns = self.returns[-self.max_len:]
    def batch_gen(self):
        np.random.shuffle(self.keys)
        batch = np.array_split(self.keys,self.max_len/self.batch_size)
        for i in batch:
            state = np.take(self.states,i,0)
            action = np.take(self.actions,i,0)
            log_prob = np.take(self.logprobs,i,0)
            returns = np.take(self.returns,i,0)
            rewards = np.take(self.rewards,i,0)
            advantages = np.take(self.advantages,i,0)
            yield state,log_prob,action,returns,advantages,rewards




    def __len__(self):
        #print(len(self.masks))
        return len(self.states)

def log_episode(log_file,episode,episode_reward,step,act_loss=0,crit_loss=0,new = False):
    data = [[episode,episode_reward,step,act_loss,crit_loss]]
    if new:
        try:
            os.remove(log_file)
        except:
            print("no log file found")
    with open(log_file, 'a', newline="") as file:
        csvwriter = csv.writer(file) # 2. create a csvwriter object
        csvwriter.writerows(data) # 5. write the rest of the data
def log_reward(reward_log,data,new=False):
    if new:
        try:
            os.remove(reward_log)
        except:
            print("reward log file not found")
    else:
        data = data.tolist()
    with open(reward_log, 'a', newline="") as file:
        csvwriter = csv.writer(file) # 2. create a csvwriter object
        csvwriter.writerow(data) # 5. write the rest of the data

def check_log(filename):
    files = os.listdir("../logs/")
    filecode = len(files)+1
    filename = '../logs/ '+filename + "_"+str(filecode)+ ".csv"
    return filename

def run_episode(actor,critic,STEPS_PER_EPISODE,rubuff,ruff_s,episode):
    eps_states = [[] for i in range(len(ruff_s))]
    eps_actions = [[] for i in range(len(ruff_s))]
    eps_rewards = [[] for i in range(len(ruff_s))]
    eps_critic_value = [[] for i in range(len(ruff_s))]
    eps_log_probs = [[] for i in range(len(ruff_s))]
    masks=[[] for i in range(len(ruff_s))]
    rewards=[[] for i in range(len(ruff_s))]
    rets = [[] for i in range(len(ruff_s))]
    advs = [[] for i in range(len(ruff_s))]
    end_flag = [0 for i in range(len(ruff_s))]
    start_t = time.time()
    for step in range(STEPS_PER_EPISODE):
        print(step)
        #print(end_flag)
        global kc, kd
        kc = kc**kd
        for i,ru in enumerate(ruff_s):
            if not ru.is_end():
                state_curr = ru.get_state()
                mu,sigma = actor([state_curr])
                critic_value = critic(state_curr)
                pos_inc, freq, actions, log_probs = ru.action_select(mu,sigma)
                ru.set_frequency(freq)
                ru.phase_modulator()
                ru.update_policy(actions)
                ru.update_target_pos(pos_inc)
                ru.move()
                try:
                    eps_states[i].append(state_curr)
                except:
                    print(i)
                eps_actions[i].append(np.array(actions).reshape((1,16)))
                eps_log_probs[i].append(log_probs)
                eps_critic_value[i].append(critic_value)
        #append state,actions,log_probs,critic_value
        #end for
        p.stepSimulation()

        for i,ru in enumerate(ruff_s):
            if not end_flag[i]:

                new_state = ru.get_state()
                reward,re = ru.get_reward(episode,step,kc)
                rewards[i].append(re)
                eps_rewards[i].append(np.array(reward).reshape((1,1)))

                if ru.is_end() and not end_flag[i]:
                    masks[i].append(0)
                    end_flag[i] = 1
                    critic_value = critic(new_state)
                    eps_critic_value[i].append(critic_value)
                    ret,adv = get_advantages(eps_critic_value[i], masks[i], eps_rewards[i])
                    rets[i].append(ret)
                    advs[i].append(adv)
                elif not end_flag[i]:
                    masks[i].append(1)
    #rew_mean = np.mean(np.array(rewards),axis=1)
    #critic_value = critic(new_state)
    #eps_critic_value.append(critic_value)
    #ret,adv = get_advantages(eps_critic_value, masks, eps_rewards)
    for i,ru in enumerate(ruff_s):
        if not end_flag[i]:
            new_state = ru.get_state()
            critic_value = critic(new_state)
            eps_critic_value[i].append(critic_value)
            ret,adv = get_advantages(eps_critic_value[i], masks[i], eps_rewards[i])
            rets[i].append(ret)
            advs[i].append(adv)

    rubuff.states = np.concatenate([np.concatenate(st,axis=0) for st in eps_states],axis=0)
    rubuff.actions = np.concatenate([np.concatenate(act,axis=0) for act in eps_actions],axis=0)
    rubuff.rewards = np.concatenate([np.concatenate(rew,axis=0) for rew in eps_rewards],axis=0)
    rubuff.values = np.concatenate([np.concatenate(cri[:-1],axis=0) for cri in eps_critic_value],axis=0)
    rubuff.logprobs = np.concatenate([np.concatenate(lp,axis=0) for lp in eps_log_probs],axis=0)
    rubuff.returns = np.concatenate([np.concatenate(r,axis=0) for r in rets],axis=0).reshape((-1,1))
    rubuff.advantages = np.concatenate([np.concatenate(a,axis=0) for a in advs],axis=0)

    rubuff.states = (rubuff.states-np.mean(rubuff.states,0))/(np.std(rubuff.states,0)+1e-10)
    #rubuff.append(eps_states,eps_actions,eps_rewards,eps_critic_value,eps_log_probs,ret,adv)
    print(" time is {:.1f}".format(time.time()-start_t))
    return step,[0]

if __name__=="__main__":
    id  = setup_world(n_actors)
    filename =check_log(filename)
    ruff_s = [ruff(i) for i in id]
    actor = actor_Model(num_inputs, n_actions,load=LOAD)
    critic = critic_Model(num_inputs, 1,load=LOAD)

    rubuff = buffer(max_buffer,MINIBATCH_SIZE)
    for episode in range(NUM_EPISODES ):
        if episode == 0:
            log_episode(log_file,"episode","avg_eps_reward","step","act_loss","crit_loss",True)
            log_reward(reward_log,reward_list,new=1)
            save_world(bullet_file)
        reset_world(bullet_file)
        gc.collect()
        ruff_s = [ruff(i) for i in id]
        step,rew_mean = run_episode(actor,critic,STEPS_PER_EPISODE,rubuff,ruff_s,episode)
        req_step+=step
        episode_reward = np.sum(rubuff.rewards)
        print("episode: "+str(episode)+" steps: "+str(step)+" episode_reward: "+str(episode_reward))
        print("kc: "+str(kc))
        if len(rubuff)==max_buffer:
            if req_step>=100:
                for i in range(ppo_epochs):

                    for states,logprobs,actions,returns,advantages,rewards in rubuff.batch_gen():

                        act_loss,crit_loss=ruff_train(actor,critic,states,logprobs,actions,returns,advantages,rewards)

                    graph_count+=1
                save_model(actor,critic)
                req_step=0
            if episode_reward>=max_reward:
                save_model(actor,critic,1)
                max_reward = episode_reward

        else:
            print("buffer size = "+str(len(rubuff)))
        log_episode(log_file,episode,episode_reward/step,step,float(act_loss),float(crit_loss))
        #log_reward(reward_log,rew_mean,0)

    close_world()
