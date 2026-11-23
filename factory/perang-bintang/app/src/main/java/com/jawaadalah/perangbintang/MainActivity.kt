package com.jawaadalah.perangbintang

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.os.Bundle
import android.view.MotionEvent
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import kotlin.math.hypot
import kotlin.random.Random

class MainActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val gameView = GameView(this)
        setContentView(gameView)
    }

    private class GameView(context: Context) : View(context) {

        // Paints
        private val paintBackground = Paint().apply { color = Color.BLACK }
        private val paintPlayer = Paint().apply { color = Color.CYAN }
        private val paintAsteroid = Paint().apply { color = Color.GRAY }
        private val paintBullet = Paint().apply { color = Color.YELLOW }
        private val paintText = Paint().apply {
            color = Color.WHITE
            textSize = 60f
            isAntiAlias = true
        }

        // Game parameters
        private val playerWidth = 120f
        private val playerHeight = 40f
        private val playerYOffset = 150f
        private val bulletRadius = 10f
        private val bulletSpeed = 20f
        private val asteroidMinRadius = 30f
        private val asteroidMaxRadius = 80f
        private val asteroidMinSpeed = 5f
        private val asteroidMaxSpeed = 12f
        private val spawnInterval = 800L   // ms
        private val shotInterval = 300L    // ms

        // Game state
        private var screenWidth = 0
        private var screenHeight = 0
        private var playerX = 0f
        private var playerY = 0f
        private var lives = 3
        private var score = 0
        private var lastSpawnTime = 0L
        private var lastShotTime = 0L
        private var gameOver = false

        // Entities
        private data class Asteroid(var x: Float, var y: Float, var radius: Float, var speed: Float)
        private data class Bullet(var x: Float, var y: Float, var radius: Float, var speed: Float)

        private val asteroids = mutableListOf<Asteroid>()
        private val bullets = mutableListOf<Bullet>()

        init {
            // Ensure view receives touch events
            isFocusable = true
            isFocusableInTouchMode = true
        }

        override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
            super.onSizeChanged(w, h, oldw, oldh)
            screenWidth = w
            screenHeight = h
            playerX = (screenWidth / 2).toFloat()
            playerY = (screenHeight - playerYOffset)
        }

        override fun onTouchEvent(event: MotionEvent): Boolean {
            if (gameOver) {
                if (event.action == MotionEvent.ACTION_DOWN) {
                    resetGame()
                }
                return true
            }
            when (event.action) {
                MotionEvent.ACTION_DOWN, MotionEvent.ACTION_MOVE -> {
                    val touchX = event.x
                    playerX = touchX.coerceIn(playerWidth / 2, screenWidth - playerWidth / 2)
                }
            }
            return true
        }

        private fun resetGame() {
            lives = 3
            score = 0
            asteroids.clear()
            bullets.clear()
            lastSpawnTime = System.currentTimeMillis()
            lastShotTime = System.currentTimeMillis()
            gameOver = false
        }

        override fun onDraw(canvas: Canvas) {
            // Background
            canvas.drawRect(0f, 0f, screenWidth.toFloat(), screenHeight.toFloat(), paintBackground)

            // Update game if not over
            if (!gameOver) {
                val now = System.currentTimeMillis()

                // Spawn asteroids
                if (now - lastSpawnTime > spawnInterval) {
                    val radius = Random.nextFloat() * (asteroidMaxRadius - asteroidMinRadius) + asteroidMinRadius
                    val xPos = Random.nextFloat() * (screenWidth - 2 * radius) + radius
                    val speed = Random.nextFloat() * (asteroidMaxSpeed - asteroidMinSpeed) + asteroidMinSpeed
                    asteroids.add(Asteroid(xPos, -radius, radius, speed))
                    lastSpawnTime = now
                }

                // Auto shoot
                if (now - lastShotTime > shotInterval) {
                    bullets.add(Bullet(playerX, playerY - playerHeight / 2, bulletRadius, bulletSpeed))
                    lastShotTime = now
                }

                // Update asteroids
                val asteroidIter = asteroids.iterator()
                while (asteroidIter.hasNext()) {
                    val a = asteroidIter.next()
                    a.y += a.speed
                    // Collision with player
                    if (hypot((a.x - playerX), (a.y - playerY)) < a.radius + playerHeight / 2) {
                        lives--
                        asteroidIter.remove()
                        if (lives <= 0) {
                            gameOver = true
                        }
                        continue
                    }
                    // Remove off-screen
                    if (a.y - a.radius > screenHeight) {
                        asteroidIter.remove()
                    }
                }

                // Update bullets
                val bulletIter = bullets.iterator()
                while (bulletIter.hasNext()) {
                    val b = bulletIter.next()
                    b.y -= b.speed
                    var hit = false
                    val astIter = asteroids.iterator()
                    while (astIter.hasNext()) {
                        val a = astIter.next()
                        if (hypot((a.x - b.x), (a.y - b.y)) < a.radius + b.radius) {
                            score += 10
                            hit = true
                            astIter.remove()
                            break
                        }
                    }
                    if (hit) {
                        bulletIter.remove()
                    } else if (b.y + b.radius < 0) {
                        bulletIter.remove()
                    }
                }
            }

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
                canvas.drawCircle(b.x, b.y, b.radius, paintBullet)
            }

            // Draw UI
            canvas.drawText("Score: $score", 20f, 70f, paintText)
            canvas.drawText("Lives: $lives", screenWidth - 250f, 70f, paintText)

            if (gameOver) {
                val text = "Game Over"
                val textWidth = paintText.measureText(text)
                canvas.drawText(text, (screenWidth - textWidth) / 2, (screenHeight / 2).toFloat(), paintText)
                val hint = "Tap to Restart"
                val hintWidth = paintText.measureText(hint)
                canvas.drawText(hint, (screenWidth - hintWidth) / 2, (screenHeight / 2 + 80).toFloat(), paintText)
            }

            // Schedule next frame
            postInvalidateDelayed(16)
        }
    }
}