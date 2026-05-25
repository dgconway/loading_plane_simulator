# loading_plane_simulator
Animating different techniques for passengers to load onto planes

# Setup
To run the python version of this app, run 

```
python main.py 
```

To run the typescript version of this app, run 
```
npm i
npm run dev
```
while inside the web/ folder. 

# Description 

We simulate a flight as 10 rows of 2 seats each. This is for simplicity and to make the animations finish faster. This is a total of 20 passengers on the plane. 
The first row is 'first class' which is functionally identical to the rest of the plane. 

There are 3 toggles in the frontend: 
1. Time to move 1 row: In seconds, the amount of time it takes a passenger to move 1 row 
2. Time to store bags and take seat: In seconds, the amount of time it takes a passenger to store their bags once they are in the correct row
3. Time to move past passenger in their row: If another passenger is seated in their row, this is the additional time required to get past them to sit down. 

Each passenger should be represented as a blue dot. That dot should turn orange when they are in the appropriate row and are putting their bad up, and then red if they are waiting for another passenger in their row to depart to get past them. Then they should turn green once they are seated. 

There should be a counter in the top right that tracks the total time elapsed since the first passenger boarded. This should be in seconds. 

There should be a helpful legend on this application to explain to a watcher what the different colors mean. 

There should be a series of checkboxes: 
1. Random passenger order: 
2. Back to front: Start with passengers in the last row and work forwards, using the window seat passenger first. 
3. Front to back: Start with passengers in the first row and work backwards, using the window seat passenger first. 
4. One per row: Start with the passenger in window seat in row 10, then the window seat in row 9, then the window seat in row 8, and so on. Then once that's done, do the same for the aisle seat. 

A passenger should always enter the aisle as soon as there's room at the entrance, potentially taking their seat before the prior passenger is done

If a passenger wants to move to aisle 6 but there is a passenger putting their bag up in aisle 5, then the passenger who wants to move to aisle 6 will need to wait in aisle 4. 