# import opennsfw2 as n2

# # OpenNSFW2: python wrapper for OpenNSFW model
# # Lower indicates better content (safer). Current threshold is 0.5.

# def is_image_safe(image_path, threshold=0.5):
#     """
#     Determines if a single image is safe based on a threshold.
    
#     :param image_path: Path to the image.
#     :param threshold: Safety threshold (default is 0.5).
#     :return: Tuple of (score, 'Safe' or 'NSFW')
#     """
#     score = n2.predict_image(image_path)
#     label = "Safe" if score < threshold else "NSFW"
#     return score, label


# def classify_images_safety(image_paths, threshold=0.5):
#     """
#     Classifies a list of images as Safe or NSFW based on the threshold.
    
#     :param image_paths: List of image paths.
#     :param threshold: Probability threshold (default is 0.5).
#     :return: Dictionary with image paths as keys and (score, label) as values.
#     """
#     raw_scores = n2.predict_images(image_paths)
#     results = {}
#     for path, score in raw_scores.items():
#         label = "Safe" if score < threshold else "NSFW"
#         results[path] = (score, label)
#     return results

