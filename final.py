import face_recognition
import cv2
import sqlite3 as lite
import sys
import numpy as np
import threading
import dlib
from skimage import io
import sys
import MySQLdb
import sched, time
from PIL import Image
from skimage import io
import matplotlib.pyplot as plt
from threading import Timer
import sys
from multiprocessing.pool import ThreadPool

# time scheduler to store in the server 
# every other 60 seconds in order to avoid 
# resending of the same picture of the unknown person
s = sched.scheduler(time.time, time.sleep)


#
# within the connection 
# get the last value of the ID in the row 
# check if it is null
# assign a new id and return
#
def generateId(myConnection):
    with myConnection:
        cur = myConnection.cursor()
        cur.execute(" select max(id) from images")
        ((id,),) = cur.fetchall()
    myConnection
    
    if (id >0):
        newId = id + 1
    else:
        newId = 1 
        
    return newId
#
# Derive all the names,images where state = 1
# Learn and Store
# Delete all the columns where state is 1 and 0
#
def learn(myConnection):
    id = 0
    
    with myConnection:
        
        cur = myConnection.cursor()
        cur.execute("Select name, image, id FROM images WHERE state = 1")
        rows = cur.fetchall()
       
        '''
        convert each BLOB to image
        learn the image
        Delete
        '''
        for row in rows:
            #print "%s, %s" % (row[0], row[1])
            
            name ='images/Output%d.jpg' % (id,)
            names = row[0]
            
            print names
            
            with open(name, "wb") as output_file:
                output_file.write(row[1])
                
            #Learn
            unknown_image = face_recognition.load_image_file(name)
            unknown_encoding = face_recognition.face_encodings(unknown_image)[0]
            
            # call a thread to wait 60 sec before storing to the DB
            timer_thread = threading.Thread(target=delayed_func, args=(names,unknown_encoding))
            timer_thread.start()
            
            cur.execute("DELETE FROM images WHERE id  = %s" %row[2])
            id += 1
            
        # Delete all the images and their id's beofe uploading new person            
        cur.execute("DELETE FROM images WHERE state = 0")
        
    myConnection

#
# delay the thread before the encodings are encountered from learner 
#
def delayed_func(name,unknown_encoding):
    time.sleep(60)
    storeIntoLocalDb(name,unknown_encoding)
    print "passed"
          
#
# create a client and connect to the DB
# assign the variables
# return the connection
#
def ClientCon():
    #create a client and connect to the DB
    hostname = '10.11.2.153'# 10.11.2.153
    username = 'admin'
    password = '123456'
    database = 'test'

    myConnection = MySQLdb.connect( host=hostname, user=username, passwd=password, db=database )
    
    return myConnection
    
    #cloase the connection
    myConnection.close()

#
# assign a id to a new file(image)
# get the image from the path
# keep in contents to save as BLOB with the rest of the values
#
def StoreIntoServer(count):
    frame = 'unknown/frame%d.jpg' % (count,)
    image = open(frame,'rb')
    contents = image.read()
    image.close()
    
    myConnection = ClientCon()
    
    with myConnection:
        
        cur = myConnection.cursor()

        newId = generateId(myConnection)
        
        sql = "INSERT INTO images VALUES (%s,%s,%s,%s)"
        
        ret = cur.execute(sql, [newId,contents,'',0])
#
# iterate over the STATE(row)
# if (state = 1) encountered
# proceed to learning
#
def iterate():
    myConnection = ClientCon()
    
    with myConnection:
        cur = myConnection.cursor()
        
        cur.execute("SELECT state FROM images")
        states = cur.fetchall()
        
        
        for state in states:
            
            (state,) = state
            
            print "this is a state ",state
            if (state == 1):
                learn(myConnection)
#
#          Local Database
# get the last value of the ID in a row
# store with it's new id and encodings of known people 
#
def storeIntoLocalDb(name,unknown_face_encoding):
    print 'storing in the Loacal DB',name,unknown_face_encoding
    # connect to the Local database
    con = lite.connect('users2.db')
    # store new person into the database 
    print name
    with con:
        cur = con.cursor()
        # get the new id
        cur.execute("SELECT max(id) FROM Users ")
        ((id,),) = cur.fetchall()
        
        if (id >0):
            newId = id + 1
        else:
            newId = 1 
        
        # storing in the Loacal DB
        query = "INSERT INTO Users VALUES (?,?,?)"
        cur.executemany(query, [(newId,name,r,) for r in unknown_face_encoding])
    con
    
# remove the parentheses from a name    
def subString(name):
    name = name[3:-3]
    return name

#
# derive from the local DB
# get each name and the encodings 
# of the known people
#
def deriveFromSQL():
    
    con = lite.connect('users2.db')

    with con:
        cur = con.cursor()    
            
        cur.execute("SELECT DISTINCT id FROM Users")
        SQLIds = len(cur.fetchall())

        
            
        id = 0
        encoding = []
        names = []

        for r in range(id,SQLIds):
            cur.execute("SELECT DISTINCT names FROM Users WHERE id = %s" %id)
            name = cur.fetchone()
            id +=1
            names.append(name)
                
        id = 0 
        for row in range(id,SQLIds):
            cur.execute("SELECT encodings FROM Users WHERE id = %s" %id)
            encodings = cur.fetchall()
            id += 1
            encoding.append(encodings)
    con
    return names,encoding
#
# thread to iterate and compare all the encodings
# of the known people with the encodings that are
# in the lift and recongised as unknown 
# if reconised return the name to display
#
def thread(encoding,names,face_encoding,frame):
    #set it to be unknown initialli 
    name = "unknown"
    
    #derive from sql and overwite all the names and their encodings
    names,encoding = deriveFromSQL()
    
    i=0
    
    #parsing 
    while (i<= len(encoding)-1):
        
        encodingner = np.array(encoding[i])
        encodingner = np.concatenate( encodingner, axis=0 )
            
            
        match = face_recognition.compare_faces([encodingner], face_encoding)
        
        print 'i = ',i 
        
        if match[0]:
            print 'match'
            name = str(names[i])
            name = subString(name)
        i+=1
        
    return name
#
# creats a HOG detector to identify all 
# of the faces in the frame
# crop and resize to send to the GUI
#
def get_faces(frame):

    # Create a HOG face detector using the built-in dlib class
    face_detector = dlib.get_frontal_face_detector()

    detected_faces = face_detector(frame, 1)
    
    face_frames = [((x.left()-150), (x.top()-150),
                    (x.right()+50), (x.bottom()+50)) for x in detected_faces]

    return face_frames
#
# The main thread is called through this method,
# every other 5 frame is taken in order to save time,
# thread pool is set to run the iteration through 
# the encondings of unknown and known people identified in the frame
#
def recognise():
    #print("Stream " + streamNum + " is began... ")
    
    # Get a reference to webcam #0 (the default one)
    video_capture = cv2.VideoCapture(0)
    #video_capture = cv2.VideoCapture(link)
    
    # Initialize some variables
    face_locations = []
    face_encodings = []
    face_names = []
    faces = []
    
    i=0
    frameNum=0
    count = 0
    
    process_this_frame = True
    
    
    pool = ThreadPool(processes=1)
    
    names,encoding = deriveFromSQL()
    
    while True:
        # iterate over the states 
        iterate()
        
        # to avoid out of range exception
        if i > len(encoding)-1:
            i=0
            
        # Grab a single frame of video
        ret, frame = video_capture.read()
        

        # Resize frame of video to 1/3 size for faster face recognition processing
        small_frame = cv2.resize(frame, (0, 0), fx=0.35, fy=0.35)

        # Only process every other frame of video to save time
        if process_this_frame:
            
            if frameNum % 5 == 0:
                
                # Find all the faces and face encodings in the current frame of video
                face_locations = face_recognition.face_locations(small_frame)
                
                print 'es hasam stex',i #,encodingner

                face_names = []


                print face_locations

                for face_location in face_locations:

                    face_encodings = face_recognition.face_encodings(small_frame, face_locations)

                    for face_encoding in face_encodings:

                        async_result = pool.apply_async(thread, (encoding,names,face_encoding,frame))

                        name = async_result.get()

                        # Detected faces
                        detected_faces = get_faces(frame)

                        # Crop faces and plot
                        if name == 'unknown' :
                            
                            '''
                            check all the faces recognised as unknown 
                            crop and send to the DB individually
                            '''
                            for n, face_rect in enumerate(detected_faces):
                                face = Image.fromarray(frame).crop(face_rect)
                                image = np.array(face)
                                
                                # save frame as JPEG file                            
                                cv2.imwrite("unknown/frame%d.jpg" % count, image)
                                
                            # run the thread every 60 seconds
                            threading=Timer(50, StoreIntoServer(count))
                            threading.start()
                            count += 1
                            
                        # add the name of the recognised people o the list
                        face_names.append(name)
                        
        # increase the fream number to be multiple of 5
        frameNum = frameNum + 1
        
        process_this_frame = not process_this_frame
        
        
        # Display the results
        for (top, right, bottom, left), name in zip(face_locations, face_names):
            # Scale back up face locations since the frame we detected in was scaled to 1/4 size
            top *= 3
            right *= 3
            bottom *= 3
            left *= 3

            # Draw a box around the face
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)


            # Draw a label with a name below the face
            cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 0, 255), cv2.FILLED)
            font = cv2.FONT_HERSHEY_DUPLEX
            cv2.putText(frame, name, (left + 6, bottom - 6), font, 1.0, (255, 255, 255), 1)

        # Display the resulting image
        cv2.imshow('Video', frame)

        # Hit 'q' on the keyboard to quit!
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Release handle to the webcam
    video_capture.release()
    cv2.destroyAllWindows()
