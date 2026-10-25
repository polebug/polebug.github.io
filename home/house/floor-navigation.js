// Pick actual world-space floor volumes so hotspots follow camera and viewport changes.
export function createFloorNavigation({ THREE, scene, camera, renderer, floors, top, useView }) {
  const canvas = renderer.domElement;
  const highlightOpacity = .32;
  const labels = ['一层', '二层', '三层'];
  const bounds = new THREE.Box3().setFromObject(scene.getObjectByName('BAKED_floors'));
  const ray = new THREE.Raycaster(), pointer = new THREE.Vector2();
  const group = new THREE.Group();
  scene.add(group);
  const meshes = floors.map((range, i) => {
    const bottom = range[0], upper = i < 2 ? floors[i + 1][0] : top;
    let geometry = new THREE.BoxGeometry(bounds.max.x - bounds.min.x + .06, upper - bottom - .04, bounds.max.z - bounds.min.z + .06);
    if (i === 2) {
      // Match the 27-degree gable in assets/blender/scripts/house_spec.py.
      // Keep the short knee walls: the attic is a gabled prism, not a box.
      const halfWidth = (bounds.max.x - bounds.min.x + .06) / 2;
      const height = upper - bottom;
      const knee = height - Math.tan(27 * Math.PI / 180) * halfWidth;
      const profile = new THREE.Shape();
      profile.moveTo(-halfWidth, -height / 2);
      profile.lineTo(halfWidth, -height / 2);
      profile.lineTo(halfWidth, knee - height / 2);
      profile.lineTo(0, height / 2);
      profile.lineTo(-halfWidth, knee - height / 2);
      profile.closePath();
      geometry.dispose();
      const depth = bounds.max.z - bounds.min.z + .06;
      geometry = new THREE.ExtrudeGeometry(profile, { depth, bevelEnabled: false, steps: 1 });
      geometry.translate(0, 0, -depth / 2);
    }
    const material = new THREE.MeshBasicMaterial({ color: 0xffcb78, transparent: true, opacity: 0, depthWrite: false, depthTest: false, toneMapped: false });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set((bounds.min.x + bounds.max.x) / 2, (bottom + upper) / 2, (bounds.min.z + bounds.max.z) / 2);
    mesh.renderOrder = 100;
    mesh.userData.floor = i;
    const edge = new THREE.LineSegments(new THREE.EdgesGeometry(geometry), new THREE.LineBasicMaterial({ color: 0xffedbd, transparent: true, opacity: 1, depthTest: false, depthWrite: false, toneMapped: false }));
    // Real geometry gives the outline consistent thickness across WebGL implementations.
    const points = edge.geometry.attributes.position;
    const outlineMaterial = new THREE.MeshBasicMaterial({ color: 0xffedbd, transparent: true, opacity: .95, depthTest: false, depthWrite: false, toneMapped: false });
    for (let n = 0; n < points.count; n += 2) {
      const a = new THREE.Vector3().fromBufferAttribute(points, n);
      const b = new THREE.Vector3().fromBufferAttribute(points, n + 1);
      const direction = b.clone().sub(a);
      const stroke = new THREE.Mesh(new THREE.CylinderGeometry(.024, .024, direction.length(), 6), outlineMaterial);
      stroke.position.copy(a).add(b).multiplyScalar(.5);
      stroke.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize());
      stroke.renderOrder = 102;
      edge.add(stroke);
    }
    edge.visible = false; edge.renderOrder = 101; mesh.add(edge); group.add(mesh);
    return mesh;
  });
  // Thin world-space slabs track the ceiling/floor even while looking around.
  const roomGroup = new THREE.Group();
  scene.add(roomGroup);
  const portals = [1, 2].map(level => {
    const geometry = new THREE.BoxGeometry(bounds.max.x - bounds.min.x + .7, .32, bounds.max.z - bounds.min.z + .08);
    const material = new THREE.MeshBasicMaterial({ color: 0xffcb78, transparent: true, opacity: 0, depthTest: false, depthWrite: false, toneMapped: false });
    const slab = new THREE.Mesh(geometry, material);
    slab.position.set((bounds.min.x + bounds.max.x) / 2, floors[level][0] - .14, (bounds.min.z + bounds.max.z) / 2);
    slab.userData.level = level; slab.renderOrder = 100;
    roomGroup.add(slab); return slab;
  });
  // Downstairs belongs to the front cutaway band, not the horizontal room floor.
  const downMask = new THREE.Mesh(
    new THREE.PlaneGeometry(bounds.max.x - bounds.min.x + .7, 200),
    new THREE.MeshBasicMaterial({ color: 0xffcb78, transparent: true, opacity: 0, depthTest: false, depthWrite: false, toneMapped: false, side: THREE.DoubleSide })
  );
  downMask.renderOrder = 100;
  roomGroup.add(downMask);
  roomGroup.visible = false;
  const facade = new THREE.Plane(new THREE.Vector3(0, 0, 1), -bounds.max.z);
  const point = new THREE.Vector3();
  const style = document.createElement('style');
  style.textContent = `#floor-back{position:fixed;z-index:5;top:16px;left:16px;border:1px solid #ffffff40;border-radius:30px;background:#20231ec9;backdrop-filter:blur(12px);color:#fff;padding:10px 15px;font:13px system-ui;cursor:pointer}#floor-back[hidden]{display:none}#floor-tip{position:fixed;z-index:5;pointer-events:none;background:#24231ef2;color:#fff0ca;border:1px solid #f6d691a6;box-shadow:0 4px 18px #0005;border-radius:9px;padding:9px 13px;font:600 13px system-ui;white-space:nowrap}#floor-tip[hidden]{display:none}.floor-key{position:fixed;left:16px;top:16px;z-index:6;opacity:0;pointer-events:none}.floor-key:focus-visible{opacity:1;pointer-events:auto;padding:10px 15px;border-radius:20px;background:#20231e;color:white;border:1px solid #ffe8bd}#floor-back:focus-visible{outline:2px solid #ffe8bd;outline-offset:3px}`;
  document.head.appendChild(style);
  const back = document.createElement('button'); back.id = 'floor-back'; back.textContent = '← Back to house'; back.hidden = true; back.onclick = () => useView('总览'); document.body.appendChild(back);
  const tip = document.createElement('div'); tip.id = 'floor-tip'; tip.hidden = true; document.body.appendChild(tip);
  let outside = true, currentFloor = -1, hovered = -1, down = null;
  function highlight(index) {
    hovered = index;
    meshes.forEach((m, i) => { m.material.opacity = outside && i === index ? highlightOpacity : 0; m.children[0].visible = outside && i === index; });
    portals.forEach(slab => { const target = slab.userData.level === currentFloor ? currentFloor - 1 : currentFloor + 1; slab.material.opacity = !outside && target === index && index > currentFloor ? .3 : 0; });
    downMask.material.opacity = !outside && currentFloor > 0 && index === currentFloor - 1 ? .3 : 0;
    canvas.style.cursor = index >= 0 ? 'pointer' : outside ? 'default' : 'grab';
    tip.hidden = index < 0;
    if (index >= 0) tip.textContent = outside ? `Enter ${index + 1}F →` : index > currentFloor ? `↑ Up to ${index + 1}F` : `↓ Down to ${index + 1}F`;
  }
  function pick(event) {
    const rect = canvas.getBoundingClientRect();
    pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
    camera.updateMatrixWorld(); group.updateMatrixWorld(true); roomGroup.updateMatrixWorld(true);
    ray.setFromCamera(pointer, camera);
    if (outside) return ray.intersectObjects(meshes, false)[0]?.object.userData.floor ?? -1;
    const active = portals.filter(slab => slab.userData.level === currentFloor + 1);
    const hit = ray.intersectObjects(active, false)[0];
    if (hit) return hit.object.userData.level === currentFloor ? currentFloor - 1 : currentFloor + 1;
    // Also include the exposed bands above/below the room's front beam.
    if (ray.ray.intersectPlane(facade, point) && point.x >= bounds.min.x - .35 && point.x <= bounds.max.x + .35) {
      if (currentFloor < 2 && point.y >= floors[currentFloor + 1][0] - .3) return currentFloor + 1;
      if (currentFloor > 0 && point.y <= floors[currentFloor][0] + .02) return currentFloor - 1;
    }
    return -1;
  }
  canvas.addEventListener('pointermove', e => {
    if (down && Math.hypot(e.clientX - down.x, e.clientY - down.y) >= 8) down.dragged = true;
    highlight(down?.dragged ? -1 : pick(e));
    tip.style.left = Math.max(8, Math.min(innerWidth - 125, e.clientX + 14)) + 'px';
    tip.style.top = Math.max(8, Math.min(innerHeight - 46, e.clientY + 14)) + 'px';
  });
  canvas.addEventListener('pointerleave', () => { down = null; highlight(-1); });
  canvas.addEventListener('pointercancel', () => { down = null; highlight(-1); });
  canvas.addEventListener('pointerdown', e => { down = { x: e.clientX, y: e.clientY, floor: pick(e) }; });
  canvas.addEventListener('pointerup', e => {
    const hit = pick(e);
    if (down && !down.dragged && hit >= 0 && hit === down.floor && Math.hypot(e.clientX - down.x, e.clientY - down.y) < 8) useView(labels[hit]);
    down = null;
  });
  const keys = labels.map((label, i) => {
    const b = document.createElement('button'); b.className = 'floor-key'; b.textContent = `Enter ${i + 1}F`;
    b.onfocus = () => { highlight(i); tip.hidden = true; }; b.onblur = () => highlight(-1);
    b.onclick = () => { useView(label); back.focus(); }; document.body.appendChild(b); return b;
  });
  addEventListener('keydown', e => { if (e.key === 'Escape' && !outside) { useView('总览'); keys[0].focus(); } });
  return {
    setView(label) { outside = label === '总览'; currentFloor = labels.indexOf(label); document.documentElement.dataset.houseFloor = outside ? 'overview' : String(currentFloor + 1); group.visible = outside; roomGroup.visible = !outside; downMask.position.set((bounds.min.x + bounds.max.x) / 2, (floors[currentFloor]?.[0] ?? 0) + .02 - 100, bounds.max.z); downMask.visible = !outside && currentFloor > 0; portals.forEach(slab => { slab.visible = !outside && (slab.userData.level === currentFloor || slab.userData.level === currentFloor + 1); }); back.hidden = outside; keys.forEach(b => { b.hidden = !outside; }); highlight(-1); },
    update() { if (hovered >= 0 && outside) meshes[hovered].material.opacity = highlightOpacity; }
  };
}
