import os
import warnings
from argparse import ArgumentParser

import cv2
import numpy
import time

warnings.filterwarnings("ignore")


class ONNXDetect:
    def __init__(self, args, onnx_path, session=None):
        self.session = session
        if self.session is None:
            assert onnx_path is not None
            assert os.path.exists(onnx_path)
            from onnxruntime import InferenceSession
            self.session = InferenceSession(onnx_path,
                                            providers=['CUDAExecutionProvider'])

        self.inputs = self.session.get_inputs()[0]
        self.confidence_threshold = 0.25
        self.iou_threshold = 0.7
        self.input_size = args.input_size
        shape = (1, 3, self.input_size, self.input_size)
        image = numpy.zeros(shape, dtype='float32')
        for _ in range(10):
            self.session.run(output_names=None,
                             input_feed={self.inputs.name: image})

    def __call__(self, image):
        image, scale = self.resize(image, self.input_size)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = image.transpose((2, 0, 1))[::-1]
        image = image.astype('float32') / 255
        image = image[numpy.newaxis, ...]

        outputs = self.session.run(output_names=None,
                                   input_feed={self.inputs.name: image})
        outputs = numpy.transpose(numpy.squeeze(outputs[0]))

        # Lists to store the bounding boxes, scores, and class IDs of the detections
        boxes = []
        scores = []
        class_indices = []

        # Iterate over each row in the outputs array
        for i in range(outputs.shape[0]):
            # Extract the class scores from the current row
            classes_scores = outputs[i][4:]

            # Find the maximum score among the class scores
            max_score = numpy.amax(classes_scores)

            # If the maximum score is above the confidence threshold
            if max_score >= self.confidence_threshold:
                # Get the class ID with the highest score
                class_id = numpy.argmax(classes_scores)

                # Extract the bounding box coordinates from the current row
                image, y, w, h = outputs[i][0], outputs[i][1], outputs[i][2], outputs[i][3]

                # Calculate the scaled coordinates of the bounding box
                left = int((image - w / 2) / scale)
                top = int((y - h / 2) / scale)
                width = int(w / scale)
                height = int(h / scale)

                # Add the class ID, score, and box coordinates to the respective lists
                class_indices.append(class_id)
                scores.append(max_score)
                boxes.append([left, top, width, height])

        # Apply non-maximum suppression to filter out overlapping bounding boxes
        indices = cv2.dnn.NMSBoxes(boxes, scores, self.confidence_threshold, self.iou_threshold)

        # Iterate over the selected indices after non-maximum suppression
        nms_outputs = []
        for i in indices:
            # Get the box, score, and class ID corresponding to the index
            box = boxes[i]
            score = scores[i]
            class_id = class_indices[i]
            nms_outputs.append([*box, score, class_id])
        return nms_outputs

    @staticmethod
    def resize(image, input_size):
        shape = image.shape

        ratio = float(shape[0]) / shape[1]
        if ratio > 1:
            h = input_size
            w = int(h / ratio)
        else:
            w = input_size
            h = int(w * ratio)
        scale = float(h) / shape[0]
        resized_image = cv2.resize(image, (w, h))
        det_image = numpy.zeros((input_size, input_size, 3), dtype=numpy.uint8)
        det_image[:h, :w, :] = resized_image
        return det_image, scale



def test(args):
    # Define class labels and their associated colors
    class_labels = ["normal", "karies kecil", "karies sedang", "karies besar", "stain", "karang gigi", "lain-lain"]
    label_colors = {
        "normal": (0, 255, 0),        # Normal - Green
        "karies kecil": (0, 255, 255),   # Karies kecil - Yellow
        "karies sedang": (255, 0, 0),  # Karies sedang - Blue
        "karies besar": (0, 0, 255),    # Karies besar - Red
        "stain": (128, 0, 128),           # Stain - Purple
        "karang gigi": (0, 165, 255),   # Karang gigi - Orange
        "lain-lain": (128, 128, 128)    # Lain-Lain - Gray
    }

    # Load model
    #model = ONNXDetect(args, onnx_path='yolov8_352.onnx')
    model = ONNXDetect(args, onnx_path='yolov8_160.onnx')
    #model = ONNXDetect(args, onnx_path='best_352.onnx')

    source = cv2.VideoCapture(0)  # Live camera source
    if not source.isOpened():
        print("Cannot open camera")
        return


    # Variables for FPS calculation
    start_time = time.time()
    frame_counter = 0
    
    while True:
        ret, frame = source.read()
        if not ret:
            print("Can't receive frame")
            break

        image = frame.copy()
        outputs = model(image)

        for output in outputs:
            x, y, w, h, score, index = output
            label = class_labels[index]

            # Draw bounding box with corresponding color based on label
            bbox_color = label_colors[label]
            cv2.rectangle(frame, (int(x), int(y)), (int(x + w), int(y + h)), bbox_color, 2)

            # Determine text label coordinates
            text_y = y - 5 if y >= 5 else y + 20  # Shift text downwards if close to top boundary
            if y < frame.shape[0] // 2:  # If the object is in the upper part of the image
                text_y = (y + h) + 20  # Place the text below the object
            else:  # If the object is in the lower part of the image
                text_y = y - 5 - 20  # Place the text above the object

            # Display label and score with the same color as the bounding box
            label_text = f"{label}: {score:.2f}"  # Concatenate label and score
            cv2.putText(frame, label_text, (x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, bbox_color, 1)

        
        
        # Calculate FPS
        frame_counter += 1
        end_time = time.time() - start_time
        if end_time >= 1:
            fps = frame_counter / end_time
            print(f"FPS: {fps:.2f}")
            frame_counter = 0
            start_time = time.time()

        cv2.imshow('Real-time Detection', frame)
        if cv2.waitKey(1) == ord('q'):
            break
        
        

    source.release()
    cv2.destroyAllWindows()


def main():
    parser = ArgumentParser()
    parser.add_argument('--input-size', default=160, type=int)

    args = parser.parse_args()

    test(args)


if __name__ == "__main__":
    main()
