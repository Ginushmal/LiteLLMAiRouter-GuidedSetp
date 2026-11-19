for pid in $(netstat -ano 2>/dev/null | grep -E ':(8099|8100)\s' | awk '{print $NF}' | sort -u); do
  taskkill //F //PID $pid >/dev/null 2>&1
done
