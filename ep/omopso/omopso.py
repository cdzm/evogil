import copy
import random

from ep.utils.driver import Driver


class OMOPSO(Driver):
    ETA = 0.0075

    def __init__(self, population, fitnesses, dims, mutation_perturbation, mutation_variance=0, crossover_variance=0):
        super().__init__(population, dims, fitnesses, mutation_variance, crossover_variance)
        self.population = population
        self.leaders_size = len(population)  # parameter?
        self.mutation_perturbation = mutation_perturbation
        self.crowding_selector = CrowdingTournament()
        self.archive = Archive(self.ETA)
        self.leader_archive = LeaderArchive(self.leaders_size)

    def init_personal_best(self):
        for p in self.__population:
            p.best_val = copy.deepcopy(p)

    def steps(self, condI, budget=None):
        cost = 0
        gen_no = 0

        cost += self.calculate_objectives()
        self.init_leaders()
        self.init_personal_best()
        self.leader_archive.crowding()

        # print("{}: {} : {}".format(gen_no, len(self.leader_archive.archive), len(self.archive.archive)))

        for _ in condI:
            self.compute_speed()
            self.move()

            # dirty hack for unknown evolution length
            progress = cost / budget if budget else gen_no / float(len(condI))
            self.mopso_mutation(progress)

            cost += self.calculate_objectives()
            self.update_leaders()
            self.update_personal_best()

            self.leader_archive.crowding()

            print("{}: {} : {}".format(gen_no, len(self.leader_archive.archive), len(self.archive.archive)))

            if budget is not None and cost > budget:
                break
            gen_no += 1

        return cost

    def init_leaders(self):
        for p in self.__population:
            if self.leader_archive.add(copy.deepcopy(p)):
                self.archive.add(copy.deepcopy(p))


    def update_personal_best(self):
        for p in self.__population:
            # print("new: {}, best: {}".format(p.objectives, p.best_val.objectives))
            if p.dominates(p.best_val):
                # print("new best: {}".format(p.objectives))
                p.best_val = copy.deepcopy(p)


    def update_leaders(self):
        for p in self.__population:
            new_ind = copy.deepcopy(p)
            if self.leader_archive.add(new_ind):
                self.archive.add(copy.deepcopy(p))


    def calculate_objectives(self):
        for p in self.__population:
            p.objectives = [o(p.value)
                            for o in self.fitnesses]
        return len(self.__population)


    def move(self):
        for p in self.__population:
            for i in range(len(self.dims)):
                new_x = p.value[i] + p.speed[i]
                bounded_x = max(new_x, self.dims[i][0])
                bounded_x = min(bounded_x, self.dims[i][1])

                if bounded_x != new_x:
                    p.speed[i] *= -1

                p.value[i] = bounded_x


    def compute_speed(self):
        for p in self.__population:
            best_global = self.crowding_selector(self.leader_archive) if len(self.leader_archive.archive) > 1 \
                else self.leader_archive.archive[0]

            r1 = random.random()
            r2 = random.random()
            C1 = random.uniform(1.5, 2.0)
            C2 = random.uniform(1.5, 2.0)
            W = random.uniform(0.1, 0.5)

            for j in range(len(self.dims)):
                p.speed[j] = W * p.speed[j] \
                             + C1 * r1 * (p.best_val.value[j] - p.value[j]) \
                             + C2 * r2 * (best_global.value[j] - p.value[j])


    def mopso_mutation(self, evolution_progress):
        pop_len = len(self.__population)
        pop_part = int(pop_len / 3)
        uniform_mutation = UniformMutation(self.mutation_probability, self.mutation_perturbation, self.dims)
        non_uniform_mutation = NonUniformMutation(evolution_progress, self.mutation_probability,
                                                  self.mutation_perturbation, self.dims)
        map(uniform_mutation, self.__population[0:pop_part])
        map(non_uniform_mutation, self.__population[pop_part: 2 * pop_part])


    @property
    def population(self):
        return [x.value for x in self.__population]

    @population.setter
    def population(self, pop):
        self.__population = [Individual(x) for x in pop]

    def finish(self):
        return [x.value for x in self.archive] if self.archive.archive else self.population


class Mutation(object):
    def __init__(self, mutation_probability, mutation_perturbation, dims):
        self.dims = dims
        self.mutation_perturbation = mutation_perturbation
        self.mutation_probability = mutation_probability

    def do_mutation(self, p, index):
        return 0

    def __call__(self, p):
        for i in range(len(self.dims)):
            if random.random() < self.mutation_probability:
                mutation = self.do_mutation(p, i)

                p.value[i] += mutation
                p.value[i] = max(p.value[i], self.dims[i][0])
                p.value[i] = min(p.value[i], self.dims[i][1])


class UniformMutation(Mutation):
    def __init__(self, mutation_probability, mutation_perturbation, dims):
        super().__init__(mutation_probability, mutation_perturbation, dims)

    def do_mutation(self, p, index):
        return (random.random() - 0.5) * self.mutation_perturbation


class NonUniformMutation(Mutation):
    def __init__(self, evolution_progress, mutation_probability, mutation_perturbation, dims):
        super().__init__(mutation_probability, mutation_perturbation, dims)
        self.evolution_progress = evolution_progress

    def do_mutation(self, p, index):
        return self.delta(self.dims[index][1] - p.value[index]) \
            if random.random() < 0.5 \
            else self.delta(self.dims[index][0] - p.value[index])

    def delta(self, y):
        rand = random.random()
        prog = 1.0 - self.evolution_progress
        perturbation = prog ** self.mutation_perturbation
        return y * (1.0 - rand ** perturbation)


class CrowdingTournament:
    def __init__(self, tournament_size=2):
        self.tournament_size = tournament_size

    def __call__(self, pool):
        sub_pool = random.sample(pool.archive, self.tournament_size)
        return min(sub_pool, key=lambda x: x.crowd_val)


class Individual:
    def __init__(self, value):
        self.value = value
        self.best_val = None
        self.speed = [0] * len(value)
        self.crowd_val = 0
        self.objectives = []

    def __deepcopy__(self, memo):
        dup = Individual(copy.deepcopy(self.value, memo))
        dup.best_val = copy.deepcopy(self.best_val, memo)
        dup.speed = copy.deepcopy(self.speed, memo)
        dup.crowd_val = self.crowd_val
        dup.objectives = copy.deepcopy(self.objectives, memo)
        return dup

    def dominates(self, p2, eta=0):
        at_least_one = False
        for i in range(len(self.objectives)):
            if p2.objectives[i] < self.objectives[i] / (1 + eta):
                return False
            elif p2.objectives[i] > self.objectives[i] / (1 + eta):
                at_least_one = True

        return at_least_one

    def equal_obj(self, p):
        for i in range(len(self.objectives)):
            if self.objectives[i] != p.objectives[i]:
                return False
        return True


class Archive(object):
    def __init__(self, eta=0.0):
        self.archive = []
        self.eta = eta

    def __iter__(self):
        return self.archive.__iter__()

    def add(self, p):

        for l in self.archive:
            if l.dominates(p, self.eta):
                return False
            elif p.dominates(l, self.eta):
                self.archive.remove(l)
            elif l.equal_obj(p):
                return False

        self.archive.append(p)
        return True


class LeaderArchive(Archive):
    def __init__(self, size):
        super().__init__()
        self.size = size

    def add(self, p):
        added = super().add(p)
        if added and len(self.archive) > self.size:
            self.prune()
        return added

    def prune(self):
        self.crowding()
        worst_res = max(self.archive, key=lambda x: x.crowd_val)
        self.archive.remove(worst_res)

    def crowding(self):
        for p in self.archive:
            p.crowd_val = 0

        obj_n = len(self.archive[0].objectives)

        archive_len = len(self.archive)
        for i in range(obj_n):
            self.archive.sort(key=lambda x: x.objectives[i])
            obj_min = self.archive[0].objectives[i]
            obj_max = self.archive[archive_len - 1].objectives[i]

            self.archive[0].crowd_val = float('inf')
            self.archive[archive_len - 1].crowd_val = float('inf')

            for j in range(1, archive_len - 1):
                if obj_max - obj_min > 0:
                    dist = self.archive[j].objectives[i] - self.archive[j - 1].objectives[i]
                    dist /= (obj_max - obj_min)
                    self.archive[j].crowd_val += dist
                else:
                    self.archive[j].crowd_val = float('inf')

