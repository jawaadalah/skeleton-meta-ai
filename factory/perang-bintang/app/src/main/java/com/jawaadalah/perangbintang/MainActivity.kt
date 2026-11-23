package com.jawaadalah.perangbintang

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.MotionEvent
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import kotlin.math.sqrt
import kotlin.random.Random

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(GameView(this))
    }

    private class GameView(context: Context) : View(context) {
        private val handler = Handler(Looper.getMainLooper())
        private val frameRate = 16L // ~60 FPS

        // Paints
        private val paintBackground = Paint().apply { color = Color.BLACK }
        private val paintPlayer = Paint().apply { color = Color.CYAN }
        private val paintAsteroid = Paint().apply { color = Color.GRAY }
        private val paintBullet = Paint().apply { color = Color.RED }
        private val paintText = Paint().apply {
            color = Color.WHITE
            textSize = 48f
            isAntiAlias = true
        }

        // Player
        private var playerX = 0f
        private var playerY = 0f
        private val playerWidth = 120f
        private val playerHeight = 40f

        // Game objects
        private data class Asteroid(var x: Float, var y: Float, var radius: Float, var speed: Float)
        private data class Bullet(var x: Float, var y: Float, var size: Float, var speed: Float)

        private val asteroids = mutableListOf<Asteroid>()
        private val bullets = mutableListOf<Bullet>()

        // Game state
        private var score = 0
        private var lives = 3
        private var running = true
        private var lastAsteroidSpawn = 0L
        private var asteroidSpawnInterval = 1000L
        private var lastBulletFire = 0L
        private var bulletFireInterval = 300L

        init {
            // Start game loop
            handler.post(updateRunnable)
        }

        private val updateRunnable = object : Runnable {
            override fun run() {
                if (running) {
                    update()
                    invalidate()
                }
                handler.postDelayed(this, frameRate)
            }
        }

        private fun resetGame() {
            score = 0
            lives = 3
            asteroids.clear()
            bullets.clear()
            running = true
            lastAsteroidSpawn = System.currentTimeMillis()
            lastBulletFire = System.currentTimeMillis()
        }

        private fun update() {
            val now = System.currentTimeMillis()
            // Spawn asteroids
            if (now - lastAsteroidSpawn > asteroidSpawnInterval) {
                val radius = Random.nextFloat() * 30f + 20f
                val x = Random.nextFloat() * (width - 2 * radius) + radius
                val speed = Random.nextFloat() * 6f + 4f
                asteroids.add(Asteroid(x, -radius, radius, speed))
                lastAsteroidSpawn = now
            }
            // Auto fire bullets
            if (now - lastBulletFire > bulletFireInterval) {
                bullets.add(Bullet(playerX, playerY - playerHeight / 2, 10f, 15f))
                lastBulletFire = now
            }
            // Update asteroids
            val iteratorA = asteroids.iterator()
            while (iteratorA.hasNext()) {
                val a = iteratorA.next()
                a.y += a.speed
                if (a.y - a.radius > height) {
                    iteratorA.remove()
                    lives--
                    if (lives <= 0) running = false
                }
            }
            // Update bullets
            val iteratorB = bullets.iterator()
            while (iteratorB.hasNext()) {
                val b = iteratorB.next()
                b.y -= b.speed
                if (b.y + b.size < 0) {
                    iteratorB.remove()
                }
            }
            // Collision detection
            val bulletIter = bullets.iterator()
            while (bulletIter.hasNext()) {
                val b = bulletIter.next()
                val asteroidIter = asteroids.iterator()
                var hit = false
                while (asteroidIter.hasNext()) {
                    val a = asteroidIter.next()
                    val dx = b.x - a.x
                    val dy = b.y - a.y
                    val distance = sqrt(dx * dx + dy * dy)
                    if (distance < a.radius + b.size / 2) {
                        // Hit
                        asteroidIter.remove()
                        hit = true
                        score += 10
                        break
                    }
                }
                if (hit) bulletIter.remove()
            }
        }

        override fun onDraw(canvas: Canvas) {
            super.onDraw(canvas)
            // Background
            canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), paintBackground)

            // Draw player
            val left = playerX - playerWidth / 2
            val top = playerY - playerHeight / 2
            val right = playerX + playerWidth / 2
            val bottom = playerY + playerHeight / 2
            canvas.drawRect(left, top, right, bottom, paintPlayer)

            // Draw asteroids
            for (a in asteroids) {
                canvas.drawCircle(a.x, a.y, a.radius, paintAsteroid)
            }

            // Draw bullets
            for (b in bullets) {
                canvas.drawRect(
                    b.x - b.size / 2,
                    b.y - b.size,
                    b.x + b.size / 2,
                    b.y,
                    paintBullet
                )
            }

            // Draw score & lives
            canvas.drawText("Score: $score", 20f, 60f, paintText)
            canvas.drawText("Lives: $lives", width - 200f, 60f, paintText)

            // Game over
            if (!running) {
                val text = "GAME OVER\nTap to Restart"
                val lines = text.split("\n")
                val yStart = height / 2f - (paintText.textSize * lines.size) / 2
                for ((i, line) in lines.withIndex()) {
                    val textWidth = paintText.measureText(line)
                    canvas.drawText(
                        line,
                        (width - textWidth) / 2,
                        yStart + i * paintText.textSize * 1.5f,
                        paintText
                    )
                }
            }
        }

        override fun onTouchEvent(event: MotionEvent): Boolean {
            when (event.action) {
                MotionEvent.ACTION_DOWN, MotionEvent.ACTION_MOVE -> {
                    if (!running) {
                        resetGame()
                        return true
                    }
                    // Update player position, clamp within bounds
                    playerX = event.x.coerceIn(playerWidth / 2, width - playerWidth / 2)
                }
            }
            return true
        }

        override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
            super.onSizeChanged(w, h, oldw, oldh)
            // Position player at bottom center
            playerX = (w / 2).toFloat()
            playerY = h - playerHeight
        }
    }
}