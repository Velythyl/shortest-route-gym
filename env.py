import time

import gym
import numpy as np
import pyglet
from gym import spaces

from graph import Graph

REWARD_INVALID = -1000

WINDOW_W = WINDOW_H = 1000


# TODO allow cop to move faster than robber should it be needed (see paper). basically just give it d turns before the
# turn bool switches
class ShortestRouteEnv(gym.Env):
    """Custom Environment that follows gym interface"""
    metadata = {'render.modes': ['human']}

    def __init__(self, networkx_graph, origin, goal, weights=None, random_weights=(0,10)):
        super(ShortestRouteEnv, self).__init__()
        # Define action and observation space
        # They must be gym.spaces objects
        self.viewer = None
        self.reset(networkx_graph, origin, goal, weights, random_weights)

    def step(self, action):
        reward, done = self.graph.transition(action)
        if not reward:  # action was invalid
            reward = REWARD_INVALID
            print("INVALID!")

        return self.graph.position, reward, done, {}

    def reset(self, networkx_graph=None, origin=None, goal=None, weights=None, random_weights=(0,10)):
        if networkx_graph is None:
            self.graph.reset(origin, goal)
        else:
            self.action_space = gym.spaces.Discrete(len(networkx_graph.nodes))
            self.observation_space = gym.spaces.Tuple((
                gym.spaces.Discrete(len(networkx_graph.nodes)),
                gym.spaces.Discrete(len(networkx_graph.nodes))
            ))
            self.layout = None
            self.graph = Graph(networkx_graph, origin, goal, weights, random_weights)
            self._make_PRAlpha()
        return self.graph.position

    def __make_R(self, multiplier):
        self.R = self.graph.adj_mat.copy()
        self.R[self.R == -1] = np.max(self.R) * 10
        self.R = multiplier * self.R
        # Problem! If we don't do this, doesn't converge; just learns to minimize until finding dead end
        for action in range(self.R.shape[0]):
            for node in range(self.R.shape[0]):
                if self.P[action][node][self.graph.goal] == 1:
                    self.R[node, self.graph.goal] = -1 * multiplier * self.graph.dijkstra_rew  # refund entire cost of path
        pass
    # a bit weird, but allows us to redefine it easily in LongestRouteEnv
    def _make_R(self):
        self.__make_R(-1)

    def _make_PRAlpha(self):
        adj_mat = self.graph.adj_mat.copy()

        # Completely deterministic. So, really, we duplicate the adj mat len(nodes) times
        adj_mat[adj_mat >= 0] = 1
        adj_mat[adj_mat < 0] = 0

        def range_except_i(n, i):
            t = []
            for j in range(n):
                if j != i:
                    t.append(j)
            return t

        P = []
        for n in range(len(self.graph.ngraph.nodes)):
            prob_mat_for_n = adj_mat.copy()
            # p of switching to non-connected node is 0
            prob_mat_for_n[:,range_except_i(len(self.graph.ngraph.nodes), n)] = 0

            # if action's node is not connected, stay in current node
            for i in range(len(self.graph.ngraph.nodes)):
                if 1 in prob_mat_for_n[i]:
                    continue
                else:
                    prob_mat_for_n[i,i] = 1

            P.append(prob_mat_for_n)

        self.P = np.array(P)
        self._make_R()
        self.alpha = np.array(range(len(self.graph.ngraph.nodes)))
        self.alpha[self.graph.origin] = 1   # initial distribution is just the origin

    def get_dijkstra(self):
        """
        Returns the optimal path and reward for the current problem.

        @return: dijkstra path, dijkstra reward
        """
        return self.graph.dijkstra_path, self.graph.dijkstra_rew

    def render(self, mode='human', human_reading_delay=1, layout_function="spring"):
        """
        Renders the state of the env for a human

        @param mode: only "human" is implemented
        @param human_reading_delay: delay for which the render stays visible (in seconds)
        @param layout_function: Any networkx layout works here https://networkx.org/documentation/stable/reference/drawing.html#module-networkx.drawing.layout
        """

        if self.graph.was_directed:
            layout_function = "shell"

        from gym.envs.classic_control import rendering
        import matplotlib.pyplot as plt
        import networkx as nx

        if self.viewer is None:
            self.viewer = rendering.SimpleImageViewer()
            self.viewer.width = WINDOW_W
            self.viewer.height = WINDOW_H
            self.viewer.window = pyglet.window.Window(width=self.viewer.width, height=self.viewer.height,
                                                      display=self.viewer.display, vsync=False, resizable=True)
        if self.layout is None:
            self.layout = getattr(nx, f"{layout_function}_layout")(self.graph.ngraph)

        fig, ax = plt.subplots()

        colors = np.array(["cyan"] * len(self.graph.ngraph.nodes))
        colors[self.graph.goal] = "blue"
        colors[self.graph.position] = "red"

        edge_colors = []
        for edge in self.graph.ngraph.edges:
            if edge in self.graph.path_bigram:
                edge_colors.append("pink")
            elif edge in self.graph.dijkstra_bigram:
                edge_colors.append("blue")
            else:
                edge_colors.append("black")


        nx.draw_networkx_nodes(self.graph.ngraph, self.layout, cmap=plt.get_cmap('jet'), node_color=colors, node_size=500)
        nx.draw_networkx_labels(self.graph.ngraph, self.layout)
        nx.draw_networkx_edges(self.graph.ngraph, self.layout, edge_color=edge_colors, edgelist=[edge for edge in self.graph.ngraph.edges()], arrows=True, connectionstyle='arc3, rad = 0.1')
        nx.draw_networkx_edge_labels(self.graph.ngraph, self.layout, edge_labels=nx.get_edge_attributes(self.graph.ngraph, "weight"), label_pos=0.3, font_size=10)

        fig.canvas.draw()
        image_from_plot = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
        image_from_plot = image_from_plot.reshape(fig.canvas.get_width_height()[::-1] + (3,))
        plt.close(fig)

        self.viewer.imshow(image_from_plot)
        time.sleep(human_reading_delay)

class LongestRouteEnv(ShortestRouteEnv):
    def _make_R(self):
        self.__make_R(1)