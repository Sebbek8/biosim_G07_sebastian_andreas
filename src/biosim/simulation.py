# -*- coding: utf-8 -*-

"""
"""

__author__ = "Sebastian Kihle & Andreas Hoeimyr"
__email__ = "sebaskih@nmbu.no & andrehoi@nmbu.no"



from biosim.geography import Mountain, Savannah, Jungle, Desert, Ocean
from biosim.animals import Animal, Herbivore, Carnivore
from biosim.island_class import Map
import textwrap
import pandas as pd
import re
import numpy as np
import seaborn as sns

import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap


class BioSim:
    def __init__(
        self,
        island_map,
        ini_pop,
        seed,
        ymax_animals=None,
        cmax_animals=None,
        img_base=None,
        img_fmt="png",
    ):
        """
        :param island_map: Multi-line string specifying island geography
        :param ini_pop: List of dictionaries specifying initial population
        :param seed: Integer used as random number seed
        :param ymax_animals: Number specifying y-axis limit for graph showing
        animal numbers
        :param cmax_animals: Dict specifying color-code limits for animal
        densities
        :param img_base: String with beginning of file name for figures,
        including path
        :param img_fmt: String with file type for figures, e.g. 'png'

        If ymax_animals is None, the y-axis limit should be adjusted
        automatically.

        If cmax_animals is None, sensible, fixed default values should be used.
        cmax_animals is a dict mapping species names to numbers, e.g.,
           {'Herbivore': 50, 'Carnivore': 20}

        If img_base is None, no figures are written to file.
        Filenames are formed as

            '{}_{:05d}.{}'.format(img_base, img_no, img_fmt)

        where img_no are consecutive image numbers starting from 0.
        img_base should contain a path and beginning of a file name.
        """
        """
                Converts the multiline string input into a numpy array of same
                dimensions.
                :param island_map:
                """
        self.map = Map(island_map)
        self.seed = seed
        self.current_year = 0

        # the following will be initialized by _setup_graphics
        self._fig = None
        self._map_ax = None
        self._img_axis = None
        self._mean_ax = None
        self._mean_line = None

        # Adds the initial population to the map.
        self.add_population(ini_pop)

    def set_animal_parameters(self, species, params):
        """
        Set parameters for animal species.

        :param species: String, name of animal species
        :param params: Dict with valid parameter specification for species
        """

        class_dict = {'Herbivore': Herbivore, 'Carnivore': Carnivore}
        class_dict[species].new_parameters(params)

    def set_landscape_parameters(self, landscape, params):
        """
        Set parameters for landscape type.

        :param landscape: String, code letter for landscape
        :param params: Dict with valid parameter specification for landscape
        """
        self.map.biome_dict[landscape].biome_parameters(params)

    def feeding_cycle(self, prints=False):
        """
        Eating cycle for each animal in each cell

        :param prints: prints relevant actions
        :return:
        """

        # Iterates through the map.
        for cell in self.map.map_iterator():
            if prints:
                print('Current cell:', type(cell).__name__, 'Feeding')

            # Regrows food in each cell.
            cell.regrow()

            # Sorts each list in according to order of descending fitness.
            cell.present_herbivores.sort(key=lambda x: x.phi, reverse=True)
            cell.present_carnivores.sort(key=lambda x: x.phi, reverse=True)

            # Eating method for the herbivores.
            for herbivore in cell.present_herbivores:
                cell.available_food = herbivore.eat(cell.available_food)
                if prints:
                    print('Weight of herbivore:', herbivore.weight)

            # Eating method for each carnivore in cell.
            for carnivore in cell.present_carnivores:
                carnivore.hunt(cell.present_herbivores)

                # Only keeps the herbivores that survived the hunt
                alive_herbivores = [herbivore for herbivore in
                                    cell.present_herbivores if herbivore.alive]

                cell.present_herbivores = alive_herbivores

    def breeding_cycle(self, prints=False):
        """
        Method for yearly breeding for all animals

        :param prints: prints relevant actions
        :return:
        """

        # For each cell in the map.
        for cell in self.map.map_iterator():
            if prints:
                print('Current cell:', type(cell).__name__, 'Breeding')

            # Creates new list so that newborns dont breed.
            current_herbivores = cell.present_herbivores
            newborn_herbivores = []
            for herbivore in cell.present_herbivores:
                # Checks if there is born a new animal, and potentially
                # adds it to a list of newborn animals in the cell.
                new_herbivore = herbivore.breeding(len(
                    current_herbivores))
                if new_herbivore is not None:
                    newborn_herbivores.append(new_herbivore)

            # Updates the herbivores present in the cell.
            cell.present_herbivores = current_herbivores + newborn_herbivores

            # Creates new list so that newborns dont breed.
            current_carnivores = cell.present_carnivores
            newborn_carnivores = []
            for carnivore in cell.present_carnivores:
                # Checks if there is born a new animal, and potentially
                # adds it to a list of newborn animals in the cell.
                new_carnivore = carnivore.breeding((len(
                    current_carnivores)))
                if new_carnivore is not None:
                    newborn_carnivores.append(new_carnivore)

            # Updates the carnivores present in the cell.
            cell.present_carnivores = current_carnivores + newborn_carnivores

    def migration_cycle(self, prints=False):
        """
        Migration method that moves all animals on the map.

        :param prints: prints relevant actions
        :return:
        """
        # For each cell in the map.
        for cell in self.map.map_iterator():
            if prints:
                print('Current cell:', type(cell).__name__, 'migration')

            # Sorts each list in according to order of descending fitness.
            cell.present_herbivores.sort(key=lambda x: x.phi, reverse=True)
            cell.present_carnivores.sort(key=lambda x: x.phi, reverse=True)

            # Herbivores in cell at start of cycle.
            migrating_herbivores = cell.present_herbivores

            # Herbivores that leave the current cell.
            exited_herbivores = []

            # For all the herbivores in cell that has not yet moved.
            for herbivore in migrating_herbivores:
                if not herbivore.has_moved:
                    target_cell = herbivore.migrate(self.map.top,
                                                    self.map.bottom,
                                                    self.map.left,
                                                    self.map.right)
                    herbivore.has_moved = True

                    # Moves to the target cell unless it is an invalid biome.
                    if target_cell is not None:
                        target_cell.present_herbivores.append(herbivore)
                        exited_herbivores.append(herbivore)
                        if prints:
                            print('An animal moved to ',
                                  type(target_cell).__name__)

            # Updates present herbivores in the cell.
            cell.present_herbivores = [animal for animal in
                                       migrating_herbivores if animal not in
                                       exited_herbivores]

            # Carnivores in cell at start of cycle.
            migrating_carnivores = cell.present_carnivores

            # Carnivores that leave the current cell.
            exited_carnivores = []

            # For all the carnivores that have not yet moved.
            for carnivore in migrating_carnivores:
                if not carnivore.has_moved:
                    target_cell = carnivore.migrate(self.map.top,
                                                    self.map.bottom,
                                                    self.map.left,
                                                    self.map.right)
                    carnivore.has_moved = True

                    # Moves to target cell unless its an invalid biome.
                    if target_cell is not None:
                        target_cell.present_carnivores.append(carnivore)
                        exited_carnivores.append(carnivore)
                        if prints:
                            print('An animal moved to ',
                                  type(target_cell).__name__)

            # Updates the present carnivores in current cell.
            cell.present_carnivores = [animal for animal in
                                       migrating_carnivores if animal not in
                                       exited_carnivores]

    def ageing_cycle(self, prints=False):
        """
        Ages all animals on the map

        :param prints: prints relevant actions
        :return:
        """

        # For each cell in the map.
        for cell in self.map.map_iterator():
            if prints:
                print('Current cell:', type(cell).__name__, 'ageing')

            # Ages the herbivores, then the carnivores.
            for herbivore in cell.present_herbivores:
                herbivore.ageing()
                if prints:
                    print('Age:', herbivore.age)

            for carnivore in cell.present_carnivores:
                carnivore.ageing()
                if prints:
                    print('Age:', carnivore.age)

    def weight_loss_cycle(self, prints=False):
        """
        Each animal on the map loses weight

        :param prints: prints relevant actions
        :return:
        """
        for cell in self.map.map_iterator():
            if prints:
                print('Current cell:', type(cell).__name__, 'weight_loss')

            # The herbivores lose weight, then the carnivores.
            for herbivore in cell.present_herbivores:
                herbivore.lose_weight()
                if prints:
                    print('Weight after loss:', herbivore.weight)

            for carnivore in cell.present_carnivores:
                carnivore.lose_weight()
                if prints:
                    print('Weight after loss:', carnivore.weight)

    def death_cycle(self, prints=False):
        """
        Each animal has a chance of dying. Removes dead animals.

        :param prints: prints relevant actions
        :return:
        """

        # For each cell in the map.
        for cell in self.map.map_iterator():
            if prints:
                print('Current cell:', type(cell).__name__, 'death')

            # Checks if the herbivores dies, then the carnivores.
            for herbivore in cell.present_herbivores:
                herbivore.potential_death()

            for carnivore in cell.present_carnivores:
                carnivore.potential_death()

            # Removes animals killed from natural causes.
            alive_herbivores = [herbivore for herbivore in
                                cell.present_herbivores if herbivore.alive]

            dead = len(cell.present_herbivores) - len(alive_herbivores)

            if dead > 0:
                if prints:
                    print(dead, 'Herbivores died')

            # Updates living herbivores in cell.
            cell.present_herbivores = alive_herbivores

            alive_carnivores = [carnivore for carnivore in
                                cell.present_carnivores if carnivore.alive]

            dead = len(cell.present_carnivores) - len(alive_carnivores)

            if dead > 0:
                if prints:
                    print(dead, 'Carnivores died')

            # Updates living carnivores in cell.
            cell.present_carnivores = alive_carnivores

    def simulate(self, num_years, vis_years=1, img_years=None, prints=False):
        """
        Run simulation while visualizing the result.

        :param num_years: number of years to simulate
        :param vis_years: years between visualization updates
        :param img_years: years between visualizations saved to files
        :param prints: Option to print the actions in each cell.
        (default: vis_years)

        Image files will be numbered consecutively.
        """
        year = 0

        while True:

            # Yearly actions for all animals.
            self.feeding_cycle(prints)
            self.breeding_cycle(prints)
            self.migration_cycle(prints)
            self.ageing_cycle(prints)
            self.weight_loss_cycle(prints)
            self.death_cycle(prints)

            # Makes all animals able to move again next year.
            for cell in self.map.map_iterator():
                for herbivore in cell.present_herbivores:
                    herbivore.has_moved = False

                for carnivore in cell.present_carnivores:
                    carnivore.has_moved = False

            # Add a year to the counter
            year += 1
            print('Current year in sim:', year)

            # Adds the amount of simulated years to the total year
            # count for the simulation.
            if year >= num_years:
                self.current_year += year
                return

    def add_population(self, population):
        """
        Add a population to the island

        :param population: List of dictionaries specifying population
        """
        # Unpacks the coordinates and animals to add.
        # Adds new animals to a temporary list.
        for dictionary in population:
            coordinates = dictionary['loc']
            animals_to_add = []

            # Gets each new animal
            for element in dictionary['pop']:
                animals_to_add.append(element)

            # Unpacks the species value, and creates new class instance of
            # class type corresponding to species.
            # New class instance uses age and weight values from dictionary.
            for animal in animals_to_add:
                if animal['age'] < 0 or animal['weight'] < 0:
                    raise ValueError('Age and weight cannot be negative')

                animal_class = animal['species']

                if animal_class == 'Herbivore':
                    new_animal = Herbivore(animal['age'], animal['weight'])

                    if type(self.map.array_map[coordinates]).__name__ not in\
                            new_animal.legal_biomes:
                        raise ValueError('This animal cannot be placed in '
                                         'this biome')
                    self.map.array_map[coordinates].\
                        present_herbivores.append(new_animal)

                if animal_class == 'Carnivore':
                    new_animal = Carnivore(animal['age'], animal['weight'])
                    if type(self.map.array_map[coordinates]).__name__ not in\
                            new_animal.legal_biomes:
                        raise ValueError('This animal cannot be placed in '
                                         'this biome')
                    self.map.array_map[coordinates].\
                        present_carnivores.append(new_animal)

    @property
    def year(self):
        """Last year simulated."""
        return self.current_year

    @property
    def num_animals(self):
        """Total number of animals on island."""
        animal_counter = 0

        for cell in self.map.map_iterator():
            for _ in cell.present_herbivores:
                animal_counter += 1

            for _ in cell.present_carnivores:
                animal_counter += 1
        return animal_counter

    @property
    def num_animals_per_species(self):
        """
        Number of animals per species in island, as dictionary.

        :return: dictionary with number of animals per species
        """
        animal_dictionary = {}
        herbivore_counter = 0
        carnivore_counter = 0

        # Counts all animals in all cells
        for cell in self.map.map_iterator():
            for herbivore in cell.present_herbivores:
                herbivore_counter += 1

            for carnivore in cell.present_carnivores:
                carnivore_counter += 1

        animal_dictionary['Herbivore'] = herbivore_counter
        animal_dictionary['Carnivore'] = carnivore_counter

        return animal_dictionary

    @property
    def animal_distribution(self):
        """Pandas DataFrame with animal count per species for
        each cell on island."""
        list_of_all_herbivores = []
        list_of_all_carnivores = []
        list_of_rows = []
        list_of_columns = []
        for cell in self.map.map_iterator():
            list_of_all_herbivores.append(len(cell.present_herbivores))
            list_of_all_carnivores.append(len(cell.present_carnivores))
            list_of_rows.append(self.map.y)
            list_of_columns.append(self.map.x)

        distribution_dict = {'Herbivore': list_of_all_herbivores,
                             'Carnivore': list_of_all_carnivores,
                             'Row': list_of_rows, 'Col': list_of_columns}
        data_frame = pd.DataFrame(distribution_dict, columns=['Row',
                                                              'Col',
                                                              'Carnivore',
                                                              'Herbivore'])
        return data_frame

    def vis_number_of_species(self):
        animals = self.num_animals_per_species
        year = self.current_year

        return

    def heat_map_herbivores(self):
        animals = self.animal_distribution
        animals = animals.pivot("Row", "Col", "Herbivore")
        ax = sns.heatmap(animals, annot=True)
        plt.title("Heatmap of the herbivore distribution")
        plt.show()

    def heat_map_carnivores(self):
        animals = self.animal_distribution
        animals = animals.pivot("Row", "Col", "Carnivore")
        ax = sns.heatmap(animals, annot=True)
        plt.title("Heatmap of the carnivore distribution")
        plt.show()


    def create_colour_island(self):
        pass

    def _setup_graphics(self, x_lim, y_lim):
        """ Creates subplots for visualization """

        # create new figure window
        if self._fig is None:
            self._fig = plt.figure()

        # Add left subplot for images created with imshow().
        # We cannot create the actual ImageAxis object before we know
        # the size of the image, so we delay its creation.
        if self._map_ax is None:
            self._map_ax = self._fig.add_subplot(1, 2, 1)
            self._img_axis = None

        # Add right subplot for line graph of mean.
        if self._mean_ax is None:
            self._mean_ax = self._fig.add_subplot(1, 2, 2)
            self._mean_ax.set_ylim(0, y_lim)

        # needs updating on subsequent calls to simulate()
        self._mean_ax.set_xlim(0, x_lim + 1)

        if self._mean_line is None:
            mean_plot = self._mean_ax.plot(np.arange(0, x_lim),
                                           np.full(x_lim, np.nan))
            self._mean_line = mean_plot[0]
        else:
            xdata, ydata = self._mean_line.get_data()
            xnew = np.arange(xdata[-1] + 1, x_lim)
            if len(xnew) > 0:
                ynew = np.full(xnew.shape, np.nan)
                self._mean_line.set_data(np.hstack((xdata, xnew)),
                                         np.hstack((ydata, ynew)))

    def make_movie(self):
        """Create MPEG4 movie from visualization images saved."""
        pass


if __name__ == "__main__":


    geogr = """\
                   OOOOOOOOOOOOOOOOOOOOO
                   OOOOOOOOSMMMMJJJJJJJO
                   OSSSSSJJJJMMJJJJJJJOO
                   OSSSSSSSSSMMJJJJJJOOO
                   OSSSSSJJJJJJJJJJJJOOO
                   OOOOOOOOOOOOOOOOOOOOO"""

    geogr = textwrap.dedent(geogr)
    k = BioSim(island_map=geogr, ini_pop=[
        {"loc": (3, 3),
         "pop": [{"species": "Herbivore", "age": 7, "weight": 15.0}]},
        {"loc": (4, 1),
         "pop": [{"species": "Herbivore", "age": 1, "weight": 15.0},
                 {"species": "Herbivore", "age": 1, "weight": 15.0},
                 {"species": "Herbivore", "age": 1, "weight": 15.0},
                 {"species": "Herbivore", "age": 1, "weight": 15.0},
                 {"species": "Herbivore", "age": 1, "weight": 15.0},
                 {"species": "Herbivore", "age": 1, "weight": 15.0}
                 ]}
    ], seed=0)

    Carnivore.new_parameters({'DeltaPhiMax': 10})
    print(k.map.biome_map)

    print(k.add_population([
            {
                "loc": (3, 3),
                "pop": [
                    {"species": "Herbivore", "age": 9, "weight": 45.0},
                    {"species": "Herbivore", "age": 5, "weight": 17.0},
                    {"species": "Herbivore", "age": 9, "weight": 45.0},
                    {"species": "Herbivore", "age": 5, "weight": 17.0}
                ],
            },
        ]
    ))
    k.simulate(100)
    print(k.num_animals)
    print('added carnivores to simulation')
    k.add_population([
            {
                "loc": (4, 1),
                "pop": [
                    {"species": "Carnivore", "age": 3, "weight": 45.0},
                    {"species": "Carnivore", "age": 2, "weight": 17.0},
                    {"species": "Carnivore", "age": 3, "weight": 45.0},
                    {"species": "Carnivore", "age": 2, "weight": 17.0},
                ],
            },
        ])
    print(k.current_year)

    k.simulate(20)
    print(k.num_animals)
    print(k.animal_distribution)
    print(k.heat_map_herbivores())
    print(k.heat_map_carnivores())
    print(k.map.array_map[2, 1].present_herbivores)

    """
    for map_cell in k.map.map_iterator():
        print(map_cell)
    """
