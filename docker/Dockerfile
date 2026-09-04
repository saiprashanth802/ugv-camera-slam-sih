# Sightline — GPS-denied UGV navigation demo image
# Base: ROS2 Humble desktop-full (includes Gazebo Classic 11 + RViz2)
FROM osrf/ros:humble-desktop-full

SHELL ["/bin/bash", "-c"]
ENV DEBIAN_FRONTEND=noninteractive

# --- Demo stack: RTAB-Map (SLAM) + Nav2 (navigation) + TurtleBot3 (robot model) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-humble-rtabmap-ros \
      ros-humble-navigation2 \
      ros-humble-nav2-bringup \
      ros-humble-turtlebot3 \
      ros-humble-turtlebot3-msgs \
      ros-humble-turtlebot3-simulations \
      ros-humble-turtlebot3-gazebo \
      ros-humble-gazebo-ros-pkgs \
      ros-humble-teleop-twist-keyboard \
      ros-humble-rqt-image-view \
      ros-humble-tf2-tools \
    && rm -rf /var/lib/apt/lists/*

# --- GUI / debug tooling (glxgears is the passthrough smoke test) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
      mesa-utils x11-apps xterm nano less tree python3-pip \
    && rm -rf /var/lib/apt/lists/*

# TurtleBot3 waffle. NOTE: the waffle does NOT ship a depth camera -- it carries imu, lidar
# and a MONOCULAR RGB camera only (verified against ros-humble-turtlebot3-gazebo 2.3.8).
# The leftover camera_depth_* TF frames in the URDF make it look otherwise. The RGB-D that
# RTAB-Map needs comes from patch_depth_camera.py below, not from the stock model.
ENV TURTLEBOT3_MODEL=waffle
# NOTE: /usr/share/gazebo-11/models MUST stay on this path. ground_plane and sun live
# there; with GAZEBO_MODEL_DATABASE_URI empty they cannot be fetched, and the world
# then fails to load with 'Unable to find uri[model://ground_plane]'.
ENV GAZEBO_MODEL_PATH=/opt/ros/humble/share/turtlebot3_gazebo/models:/usr/share/gazebo-11/models
# Keep Gazebo off the online model DB — it stalls for minutes on a bad venue network
ENV GAZEBO_MODEL_DATABASE_URI=""
# Isolate the demo from any other ROS2 traffic on the venue LAN
ENV ROS_DOMAIN_ID=42
ENV ROS_LOCALHOST_ONLY=1

# The waffle ships an RGB-only camera; convert it to depth so RTAB-Map has RGB-D.
COPY patch_depth_camera.py /tmp/patch_depth_camera.py
RUN python3 /tmp/patch_depth_camera.py

RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc \
 && echo "export TURTLEBOT3_MODEL=waffle" >> /root/.bashrc

WORKDIR /ws
CMD ["/bin/bash"]
